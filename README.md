# auroraex [![PyPI version](https://badge.fury.io/py/auroraex.svg)](https://badge.fury.io/py/auroraex)

Command Line utility for Amazon Aurora.

Support python3 only. (use boto3)

## Settings

```sh
export AWS_ACCESS_KEY_ID=XXXXXXXXXXXXXXXXXXXX
export AWS_SECRET_ACCESS_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
export AWS_DEFAULT_REGION=xx-xxxxxxx-x
```

* support environment variables and iam role.

## Examples

#### list instance and cluster

```sh
$ auroraex list

[instances]
db01 mysql available db.m3.xlarge  ap-northeast-1c None
db02 mysql available db.m3.xlarge  ap-northeast-1c None
db03 mysql available db.m3.large ap-northeast-1c None
db04 mysql available db.m3.large ap-northeast-1c None
db05 aurora available db.t2.medium  ap-northeast-1c aurora-cluster
db06 aurora available db.t2.medium  ap-northeast-1c aurora-cluster

[clusters]
aurora-cluster available aurora  ['db05', 'db06']
...
```

#### restore aurora cluster

```sh
$ auroraex restore -s ${source-cluster-identifier} -t ${restore-cluster-identifier} -w ${writer-instance} -r ${reader-instance}
```

* use copy-on-write.

#### delete aurora cluster and child instance

```sh
$ auroraex delete_cluster -i ${delete-target-cluster-identifier}
```

## Installation

```sh
pip install auroraex
```

## Contributing

1. Fork it
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new [Pull Request](../../pull/new/master)

## Information

* [Homepage](https://github.com/toyama0919/auroraex)
* [Issues](https://github.com/toyama0919/auroraex/issues)
* [Documentation](http://rubydoc.info/gems/auroraex/frames)
* [Email](mailto:toyama0919@gmail.com)
