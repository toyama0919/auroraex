import click
import sys
import os
import time
from .logger import get_logger
from .core import Core
from .util import Util
from .validator import Validator
from datetime import datetime
from tabulate import tabulate


class Mash(object):
    pass


@click.group()
@click.option('--debug/--no-debug', default=False, help='enable debug logging')
@click.pass_context
def cli(ctx, debug):
    ctx.obj = Mash()

    ctx.obj.core = Core(debug)
    ctx.obj.client = ctx.obj.core.client
    ctx.obj.logger = get_logger(debug)


@cli.command(help='list instance and cluster')
@click.pass_context
def list(ctx):
    headers = [
        'DBInstanceIdentifier',
        'Engine',
        'DBInstanceStatus',
        'DBInstanceClass',
        'AvailabilityZone',
        'DBClusterIdentifier'
    ]
    rows = []
    for instance in ctx.obj.core.get_instances(None):
        row = [instance.get(key) for key in headers]
        rows.append(row)
    print(tabulate(rows, headers=headers))

    print("")

    headers = [
        'DBClusterIdentifier',
        'Engine',
        'Status',
    ]
    rows = []
    for cluster in ctx.obj.core.get_clusters(None):
        row = [cluster.get(key) for key in headers]
        members = cluster.get('DBClusterMembers')
        writers = [member['DBInstanceIdentifier'] for member in members if member['IsClusterWriter']]
        readers = [member['DBInstanceIdentifier'] for member in members if not member['IsClusterWriter']]
        row.append(writers)
        row.append(readers)
        rows.append(row)
    headers.append('writer')
    headers.append('readers')
    print(tabulate(rows, headers=headers))


@cli.command(help='list instance')
@click.option('--identifier', '-i', default=None)
@click.pass_context
def list_instance(ctx, identifier):
    db_instances = ctx.obj.core.get_instances(identifier)
    Util.print_json(db_instances)


@cli.command(help='list clusters')
@click.option('--identifier', '-i', default=None)
@click.pass_context
def list_cluster(ctx, identifier):
    clusters = ctx.obj.core.get_clusters(identifier)
    Util.print_json(clusters)


@cli.command(help='restore Aurora cluster and instance')
@click.option('--source_cluster_identifier', '-s', required=True)
@click.option('--target_cluster_identifier', '-t', required=True)
@click.option('--profile_cluster_identifier')
@click.option('--writer_instance_identifier', '-w', required=True)
@click.option('--reader_instance_identifier', '-r', default=[], multiple=True)
@click.option('--params', '-p', default='{}')
@click.option('--overwrite/--no-overwrite', default=False)
@click.option('--suffix', callback=Validator.validate_suffix, default=datetime.now().strftime('%Y%m%d%H%M%S'))
@click.pass_context
def restore(
        ctx,
        source_cluster_identifier,
        target_cluster_identifier,
        profile_cluster_identifier,
        writer_instance_identifier,
        reader_instance_identifier,
        params,
        overwrite,
        suffix
    ):
    tmp_target_cluster_identifier = target_cluster_identifier + '-' + suffix
    tmp_writer_instance_identifier = writer_instance_identifier + '-' + suffix
    tmp_reader_instance_identifier =[i + '-' + suffix for i in reader_instance_identifier]
    identifiers = [tmp_writer_instance_identifier] + tmp_reader_instance_identifier

    source_cluster = ctx.obj.core.get_cluster(profile_cluster_identifier) if profile_cluster_identifier else ctx.obj.core.get_cluster(source_cluster_identifier)
    writers = [member for member in source_cluster["DBClusterMembers"] if member['IsClusterWriter']]
    source_writer_instance = ctx.obj.core.get_instance(writers[0]['DBInstanceIdentifier'])

    create_db_instance_option = dict(
        DBInstanceClass=source_writer_instance['DBInstanceClass'],
        Engine='aurora',
        AvailabilityZone=source_writer_instance['AvailabilityZone'],
        DBSubnetGroupName=source_writer_instance['DBSubnetGroup']['DBSubnetGroupName'],
        DBParameterGroupName=source_writer_instance['DBParameterGroups'][0]['DBParameterGroupName'],
        DBClusterIdentifier=tmp_target_cluster_identifier
    )

    restore_db_cluster_to_point_in_time_option = dict(
        SourceDBClusterIdentifier=source_cluster_identifier,
        DBClusterIdentifier=tmp_target_cluster_identifier,
        UseLatestRestorableTime=True,
        DBSubnetGroupName=source_cluster['DBSubnetGroup'],
        VpcSecurityGroupIds=[i['VpcSecurityGroupId'] for i in source_cluster['VpcSecurityGroups']],
        RestoreType='copy-on-write',
        Tags=[
            {
                'Key': 'Name',
                'Value': tmp_target_cluster_identifier
            },
        ]
    )
    response = ctx.obj.client.restore_db_cluster_to_point_in_time(**restore_db_cluster_to_point_in_time_option)

    time.sleep(3)

    create_db_instance_option.update(eval(params))
    for identifier in identifiers:
        create_db_instance_option['DBInstanceIdentifier'] = identifier
        response = ctx.obj.client.create_db_instance(**create_db_instance_option)

    if overwrite:
        ctx.invoke(delete_cluster, cluster_identifier=target_cluster_identifier)

    ctx.obj.core.wait_for_available_cluster(tmp_target_cluster_identifier)
    response = ctx.obj.client.modify_db_cluster(
        DBClusterIdentifier=tmp_target_cluster_identifier,
        NewDBClusterIdentifier=target_cluster_identifier,
        ApplyImmediately=True,
        DBClusterParameterGroupName=source_cluster['DBClusterParameterGroup']
    )

    for identifier in identifiers:
        ctx.obj.core.wait_for_available(identifier)
        new_identifier = identifier.replace('-' + identifier.rsplit('-', 1)[-1], '')
        ctx.obj.logger.info("rename instance {0} => {1}".format(identifier, new_identifier))
        response = ctx.obj.client.modify_db_instance(
            DBInstanceIdentifier=identifier,
            NewDBInstanceIdentifier=new_identifier,
            ApplyImmediately=True,
            DBParameterGroupName=source_writer_instance['DBParameterGroups'][0]['DBParameterGroupName']
        )
        ctx.obj.core.wait_for_available(new_identifier)


@cli.command(help='delete cluster and child instance')
@click.option('--cluster_identifier', '-i', required=True)
@click.pass_context
def delete_cluster(ctx, cluster_identifier):
    identifiers = ctx.obj.core.get_cluster_member_identifiers(cluster_identifier)
    for identifier in identifiers:
        response = ctx.obj.core.delete_instance_and_wait(identifier)

    ctx.obj.core.delete_cluster_and_wait(cluster_identifier)


@cli.command(help='reboot cluster and child instance')
@click.option('--cluster_identifier', '-i', required=True)
@click.pass_context
def reboot_cluster(ctx, cluster_identifier):
    identifiers = ctx.obj.core.get_cluster_member_identifiers(cluster_identifier)
    for identifier in identifiers:
        ctx.obj.core.reboot_instance_and_wait(identifier)


@cli.command(help='reboot instance')
@click.option('--instance_identifier', '-i', required=True)
@click.pass_context
def reboot_instance(ctx, instance_identifier):
    ctx.obj.core.reboot_instance_and_wait(instance_identifier)


@cli.command(help='run command')
@click.option('--command', '-c')
@click.pass_context
def run_command(ctx, command):
    return os.system(command)


@cli.command(help='run command')
@click.pass_context
def user_parameter_groups(ctx):
    response = ctx.obj.client.describe_db_parameter_groups()
    Util.print_tabulate(response['DBParameterGroups'])


@cli.command(help='run command')
@click.option('--identifier', '-i', required=True)
@click.pass_context
def user_parameters(ctx, identifier):
    response = ctx.obj.client.describe_db_parameters(
        DBParameterGroupName=identifier,
        Source='user'
    )
    headers = ['ParameterName', 'ParameterValue', 'Description']
    Util.print_tabulate(response['Parameters'], headers=headers, strip_size=50)


@cli.command(help='run command')
@click.option('--identifier', '-i', required=True)
@click.pass_context
def user_cluster_parameters(ctx, identifier):
    response = ctx.obj.client.describe_db_cluster_parameters(
        DBClusterParameterGroupName=identifier,
        Source='user'
    )
    headers = ['ParameterName', 'ParameterValue', 'Description']
    Util.print_tabulate(response['Parameters'], headers=headers, strip_size=50)


def main():
    cli(obj={})
