import click
import sys
import os
import pprint
import time
from .logger import get_logger
from .core import *
from .util import *
from datetime import datetime

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
@click.option('--identifier', '-i', default=None)
@click.pass_context
def list(ctx, identifier):
    ctx.invoke(list_clusters, identifier=identifier)
    ctx.invoke(list_instance, identifier=identifier)

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
@click.option('--source_cluster_identifier', '-s')
@click.option('--target_cluster_identifier', '-t')
@click.option('--writer_instance_identifier', '-w')
@click.option('--reader_instance_identifier', '-r', default=[], multiple=True)
@click.option('--suffix', default=None)
@click.pass_context
def restore(ctx, source_cluster_identifier, target_cluster_identifier, writer_instance_identifier, reader_instance_identifier, suffix):
    suffix = suffix or datetime.now().strftime('%Y%m%d%H%M%S')
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

    ctx.invoke(delete, cluster_identifier=target_cluster_identifier)
    ctx.invoke(rename_tmp, cluster_identifier=tmp_target_cluster_identifier)

@cli.command(help = 'delete cluster and child instance')
@click.option('--cluster_identifier', '-i')
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
@click.option('--cluster_identifier', '-i')
def delete(cluster_identifier):
    source_cluster = core.get_cluster(cluster_identifier)
    if not source_cluster:
        logger.info("{cluster_identifier} is not exist.".format(cluster_identifier = cluster_identifier))
        return

    for member in source_cluster["DBClusterMembers"]:
        identifier = member['DBInstanceIdentifier']
        response = core.delete_instance_and_wait(identifier)

    core.delete_cluster_and_wait(cluster_identifier)

@cli.command(help = 'delete cluster and child instance')
@click.option('--cluster_identifier', '-i')
def reboot_cluster(cluster_identifier):
    source_cluster = core.get_cluster(cluster_identifier)
    if not source_cluster:
        logger.info("{cluster_identifier} is not exist.".format(cluster_identifier = cluster_identifier))
        return

    for member in source_cluster["DBClusterMembers"]:
        identifier = member['DBInstanceIdentifier']
        response = client.reboot_db_instance(
            DBInstanceIdentifier=identifier,
            ForceFailover=False
        )

@cli.command(help = 'run command')
@click.option('--command', '-c')
def run_command(command):
    return os.system(command)

def main():
    cli(obj={})
