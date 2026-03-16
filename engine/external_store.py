import os


class ExternalStore:
    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET")
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
        self.region = os.getenv("AWS_REGION") or None
        self.prefix = os.getenv("S3_PREFIX", "youtube-patrol")
        self.enabled = bool(self.bucket)
        self._client = None

    def upload_files(self, file_paths):
        if not self.enabled:
            return []
        client = self._get_client()
        uploaded = []
        for path in file_paths:
            if not path or not os.path.exists(path):
                continue
            key = f"{self.prefix}/{path.replace(os.sep, '/')}"
            client.upload_file(path, self.bucket, key)
            uploaded.append({"path": path, "key": key})
        return uploaded

    def _get_client(self):
        if self._client is not None:
            return self._client
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
        )
        return self._client
