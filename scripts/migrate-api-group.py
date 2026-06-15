#!/usr/bin/env python3
"""Export kubevoip.io Asterisk resources as clean kubevoip.com manifests."""

import argparse
import sys

import yaml
from kubernetes import client, config

REMOVE_ANNOTATION_PREFIXES = ("argocd.argoproj.io/", "kopf.zalando.org/", "kubectl.kubernetes.io/")


def clean(item: dict) -> dict:
    metadata = item["metadata"]
    annotations = {
        key: value
        for key, value in metadata.get("annotations", {}).items()
        if not key.startswith(REMOVE_ANNOTATION_PREFIXES)
    }
    result = {
        "apiVersion": "kubevoip.com/v1alpha1",
        "kind": "Asterisk",
        "metadata": {"name": metadata["name"], "namespace": metadata["namespace"]},
        "spec": item["spec"],
    }
    if metadata.get("labels"):
        result["metadata"]["labels"] = metadata["labels"]
    if annotations:
        result["metadata"]["annotations"] = annotations
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace")
    parser.add_argument("--name")
    parser.add_argument("--all-namespaces", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if not args.all_namespaces and not args.namespace:
        parser.error("provide --all-namespaces or --namespace")
    config.load_kube_config()
    api = client.CustomObjectsApi()
    if args.name:
        if not args.namespace:
            parser.error("--name requires --namespace")
        items = [api.get_namespaced_custom_object("kubevoip.io", "v1alpha1", args.namespace, "asterisks", args.name)]
    elif args.all_namespaces:
        items = api.list_cluster_custom_object("kubevoip.io", "v1alpha1", "asterisks")["items"]
    else:
        items = api.list_namespaced_custom_object("kubevoip.io", "v1alpha1", args.namespace, "asterisks")["items"]
    manifests = [clean(item) for item in items]
    if not args.apply:
        yaml.safe_dump_all(manifests, sys.stdout, sort_keys=False)
        return 0
    if not args.yes:
        parser.error("--apply requires --yes")
    for manifest in manifests:
        api.create_namespaced_custom_object(
            "kubevoip.com", "v1alpha1", manifest["metadata"]["namespace"], "asterisks", manifest
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
