import boto3
import traceback
import time
import os
import json
from .logger import get_logger

class Core:

    def __init__(self, debug):
        self.client = boto3.client('rds')
        self.logger = get_logger(debug)

    def get_cluster(self, cluster_identifier):
        clusters = self.get_clusters(cluster_identifier)
        return (None if len(clusters) == 0 else clusters[0])

    def get_clusters(self, cluster_identifier):
        option = {}
        if cluster_identifier: option['DBClusterIdentifier'] = cluster_identifier
        db_clusters = []
        try:
            db_clusters = self.client.describe_db_clusters(**option)['DBClusters']
        except Exception as e:
            return db_clusters

        return db_clusters

    def get_instance(self, identifier = None):
        instances = self.get_instances(identifier)
        return (None if len(instances) == 0 else instances[0])

    def get_instances(self, identifier):
        option = {}
        if identifier: option['DBInstanceIdentifier'] = identifier
        db_instances = []
        try:
            db_instances = self.client.describe_db_instances(**option)['DBInstances']
        except Exception as e:
            return db_instances

        return db_instances

    def wait_for_available(self, instance_identifier):
        waiter = self.client.get_waiter('db_instance_available')
        self.logger.info("waiting available instance... {instance_identifier}".format(instance_identifier=instance_identifier))
        waiter.wait(
            DBInstanceIdentifier=instance_identifier
        )

    def get_cluster_members(self, cluster_identifier):
        cluster = self.get_cluster(cluster_identifier)
        return (cluster["DBClusterMembers"] if cluster else [])

    def get_cluster_member_identifiers(self, cluster_identifier):
        members = self.get_cluster_members(cluster_identifier)
        return [member['DBInstanceIdentifier'] for member in members]

    def reboot_instance_and_wait(self, instance_identifier):
        response = self.client.reboot_db_instance(
            DBInstanceIdentifier=instance_identifier,
            ForceFailover=False
        )
        self.logger.info("rebooting instance... {instance_identifier}".format(instance_identifier=instance_identifier))
        self.wait_for_available(instance_identifier)

    def delete_instance_and_wait(self, instance_identifier):
        self.client.delete_db_instance(
            DBInstanceIdentifier=instance_identifier,
            SkipFinalSnapshot=True
        )
        self.logger.info("deleting instance... {instance_identifier}".format(instance_identifier=instance_identifier))
        waiter = self.client.get_waiter('db_instance_deleted')
        waiter.wait(
            DBInstanceIdentifier=instance_identifier
        )

    def delete_cluster_and_wait(self, cluster_identifier):
        cluster = self.get_cluster(cluster_identifier)
        if not cluster:
            self.logger.info("{cluster_identifier} is not exist.".format(cluster_identifier = cluster_identifier))
            return

        response = self.client.delete_db_cluster(
            DBClusterIdentifier=cluster_identifier,
            SkipFinalSnapshot=True
        )
        self.logger.info("deleting cluster... {cluster_identifier}".format(cluster_identifier=cluster_identifier))
        while len(self.get_clusters(cluster_identifier)) > 0:
            time.sleep(10)
