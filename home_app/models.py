from django.db import models
from accounts_app.models import User


class UploadedFile(models.Model):
    FILE_TYPES = [
        ("lebenslauf", "Lebenslauf"),
        ("rechnung", "Rechnung"),
        ("anschreiben", "Anschreiben"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploads")
    filetype = models.CharField(max_length=20, choices=FILE_TYPES)
    filelocation = models.FileField(upload_to="uploaded_documents/%Y/%m/%d/")
    file_address_key = models.CharField(max_length=200,primary_key=True)
    uploadtime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploadtime"]
        verbose_name = "Uploaded File"
        verbose_name_plural = "Uploaded Files"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["-uploadtime"]),
        ]

    def __str__(self):
        return f"{self.filetype} ({self.file_address_key})"



class LebenslaufMetadata(models.Model):
    file_key = models.ForeignKey(
        UploadedFile,
        on_delete=models.CASCADE,
        db_column="file_key",
        to_field="file_address_key",
        related_name="metadatas",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user",
        to_field="id",
        related_name="lebenslauf_metadatas",
    )

    name = models.CharField(max_length=50, blank=True, null=True)
    primary_phone = models.CharField(max_length=20, blank=True, null=True)
    primary_email = models.CharField(max_length=255, blank=True, null=True)
    urls = models.TextField(blank=True, null=True)
    linkedin = models.CharField(max_length=255, blank=True, null=True)
    github = models.CharField(max_length=255, blank=True, null=True)
    fulladdress = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    workexperiance = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "lebenslauf_metadata"
        constraints = [
            models.UniqueConstraint(fields=["file_key"], name="uq_lebenslauf_metadata_file_key")
        ]
