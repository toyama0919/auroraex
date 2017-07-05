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
@click.pass_context
def restore(ctx, source_cluster_identifier, target_cluster_identifier, writer_instance_identifier, reader_instance_identifier):
    time_string = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_target_cluster_identifier = target_cluster_identifier + '-' + time_string
    tmp_writer_instance_identifier = writer_instance_identifier + '-' + time_string
    tmp_reader_instance_identifier =[i + '-' + time_string for i in reader_instance_identifier]
    identifiers = [tmp_writer_instance_identifier].extend(tmp_reader_instance_identifier)

    source_cluster = client.describe_db_clusters(**{"DBClusterIdentifier":source_cluster_identifier})['DBClusters'][0]
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

    for tmp_identifier in identifiers:
        core.wait_for_available(tmp_identifier)
        identifier = tmp_identifier.replace('-' + time_string, '')
        response = client.modify_db_instance(
            DBInstanceIdentifier=tmp_identifier,
            NewDBInstanceIdentifier=identifier,
            ApplyImmediately=True
        )

    # cluster
    response = client.modify_db_cluster(
        DBClusterIdentifier=tmp_target_cluster_identifier,
        NewDBClusterIdentifier=target_cluster_identifier,
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

@cli.command(help = 'run command')
@click.option('--command', '-c')
def run_command(command):
    return os.system(command)

def main():
    cli(obj={})
