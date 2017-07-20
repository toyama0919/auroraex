import click
import sys
import os
import pprint
import time
from .logger import get_logger
from .core import *
from .util import *
from .validator import *
from datetime import datetime
from tabulate import tabulate

@click.group()
@click.option('--debug/--no-debug', default=False, help='enable debug logging')
def cli(debug):
    global core
    global client
    global logger

    core = Core(debug)
    client = core.client
    logger = get_logger(debug)

@cli.command(help = 'list instance and cluster')
def list():
    headers = [
        'DBInstanceIdentifier',
        'Engine',
        'DBInstanceStatus',
        'DBInstanceClass',
        'AvailabilityZone',
        'DBClusterIdentifier'
    ]
    rows = []
    for instance in core.get_instances(None):
        row = [instance.get(key) for key in headers]
        rows.append(row)
    print(tabulate(rows, headers = headers))

    print("")

    headers = [
        'DBClusterIdentifier',
        'Engine',
        'Status',
    ]
    rows = []
    for cluster in core.get_clusters(None):
        row = [cluster.get(key) for key in headers]
        members = cluster.get('DBClusterMembers')
        writers = [member['DBInstanceIdentifier'] for member in members if member['IsClusterWriter']]
        readers = [member['DBInstanceIdentifier'] for member in members if not member['IsClusterWriter']]
        row.append(writers[0])
        row.append(readers)
        rows.append(row)
    headers.append('writer')
    headers.append('readers')
    print(tabulate(rows, headers = headers))

@cli.command(help = 'list instance')
@click.option('--identifier', '-i', default=None)
def list_instance(identifier):
    db_instances = core.get_instances(identifier)
    Util.print_json(db_instances)

@cli.command(help = 'list clusters')
@click.option('--identifier', '-i', default=None)
def list_cluster(identifier):
    clusters = core.get_clusters(identifier)
    Util.print_json(clusters)

@cli.command(help = 'restore Aurora cluster and instance')
@click.option('--source_cluster_identifier', '-s', required=True)
@click.option('--target_cluster_identifier', '-t', required=True)
@click.option('--writer_instance_identifier', '-w', required=True)
@click.option('--reader_instance_identifier', '-r', default=[], multiple=True)
@click.option('--suffix', callback=Validator.validate_suffix, default=datetime.now().strftime('%Y%m%d%H%M%S'))
@click.pass_context
def restore(ctx, source_cluster_identifier, target_cluster_identifier, writer_instance_identifier, reader_instance_identifier, suffix):
    tmp_target_cluster_identifier = target_cluster_identifier + '-' + suffix
    tmp_writer_instance_identifier = writer_instance_identifier + '-' + suffix
    tmp_reader_instance_identifier =[i + '-' + suffix for i in reader_instance_identifier]
    identifiers = [tmp_writer_instance_identifier] + tmp_reader_instance_identifier

    source_cluster = core.get_cluster(source_cluster_identifier)
    writers = [member for member in source_cluster["DBClusterMembers"] if member['IsClusterWriter']]
    source_writer_instance = core.get_instance(writers[0]['DBInstanceIdentifier'])

    response = client.restore_db_cluster_to_point_in_time(
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

    time.sleep(3)

    create_db_instance_option = dict(
        DBInstanceClass=source_writer_instance['DBInstanceClass'],
        Engine='aurora',
        AvailabilityZone=source_writer_instance['AvailabilityZone'],
        DBSubnetGroupName=source_writer_instance['DBSubnetGroup']['DBSubnetGroupName'],
        DBParameterGroupName=source_writer_instance['DBParameterGroups'][0]['DBParameterGroupName'],
        DBClusterIdentifier=tmp_target_cluster_identifier
    )

    for identifier in identifiers:
        create_db_instance_option['DBInstanceIdentifier'] = identifier
        response = client.create_db_instance(**create_db_instance_option)

    ctx.invoke(delete_cluster, cluster_identifier=target_cluster_identifier)
    ctx.invoke(rename_tmp, cluster_identifier=tmp_target_cluster_identifier)

@cli.command(help = 'delete cluster and child instance')
@click.option('--cluster_identifier', '-i', required=True)
def rename_tmp(cluster_identifier):
    source_cluster = core.get_cluster(cluster_identifier)

    tmp_identifiers = [member['DBInstanceIdentifier'] for member in source_cluster["DBClusterMembers"]]

    # instance
    for tmp_identifier in tmp_identifiers:
        core.wait_for_available(tmp_identifier)
        tmp_identifier.rsplit('-', 1)
        identifier = tmp_identifier.replace('-' + tmp_identifier.rsplit('-', 1)[-1], '')
        logger.info("rename instance {0} => {1}".format(tmp_identifier, identifier))
        response = client.modify_db_instance(
            DBInstanceIdentifier=tmp_identifier,
            NewDBInstanceIdentifier=identifier,
            ApplyImmediately=True
        )

    # cluster
    new_cluster_identifier = cluster_identifier.replace('-' + cluster_identifier.rsplit('-', 1)[-1], '')
    logger.info("rename cluster {0} => {1}".format(cluster_identifier, new_cluster_identifier))
    response = client.modify_db_cluster(
        DBClusterIdentifier=cluster_identifier,
        NewDBClusterIdentifier=new_cluster_identifier,
        ApplyImmediately=True
    )

@cli.command(help = 'delete cluster and child instance')
@click.option('--cluster_identifier', '-i', required=True)
def delete_cluster(cluster_identifier):
    identifiers = core.get_cluster_member_identifiers(cluster_identifier)
    for identifier in identifiers:
        response = core.delete_instance_and_wait(identifier)

    core.delete_cluster_and_wait(cluster_identifier)

@cli.command(help = 'reboot cluster and child instance')
@click.option('--cluster_identifier', '-i', required=True)
def reboot_cluster(cluster_identifier):
    identifiers = core.get_cluster_member_identifiers(cluster_identifier)
    for identifier in identifiers:
        core.reboot_instance_and_wait(identifier)

@cli.command(help = 'reboot instance')
@click.option('--instance_identifier', '-i', required=True)
def reboot_instance(instance_identifier):
    core.reboot_instance_and_wait(instance_identifier)

@cli.command(help = 'run command')
@click.option('--command', '-c')
def run_command(command):
    return os.system(command)

def main():
    cli(obj={})
