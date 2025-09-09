
# 📄 Document Upload & Metadata Management (Django App)

The logic is divided between two decoupled Docker containers, both horizontally scalable:

1. **User Interface** – covered in this README (Django-based upload and metadata management).  
2. **Processing Service** – a separate container responsible for backend tasks:
   - Consumes document messages from Amazon SQS.  
   - Performs data extraction using Anthropic’s LLM.  
   - Loads the normalized CV data into the database for downstream usage.

## Overview

This Django app provides **secure file upload, storage, and processing** functionality with AWS integration.
It allows users to:

* Upload PDF documents (e.g., Lebenslauf/CV, Rechnungen, Anschreiben).
* Store files in **Amazon S3**.
* Send file metadata to an **Amazon SQS** queue for further processing (e.g., extraction, AI enrichment).
* Manage uploaded files (view, edit, delete).
* Store and edit structured metadata for uploaded Lebenslauf documents.

The app uses:

* **Django ORM** for persistence.
* **AWS S3 & SQS** (via `boto3`) for file storage and messaging.
* **Custom services layer** for validation, monitoring, and AWS integration.
* **DRF + JWT** for API-based authentication.

---

## ⚙️ Features

### 🔐 Authentication

* Custom `User` model with extended fields (phone, birthdate, wallet).
* Login/logout, registration, and JWT token support.
* Username or email-based login.

### 📂 File Upload & Management

* Upload PDF files with:

  * File size validation (`MAX_FILE_SIZE_KB`).
  * Extension validation (PDF only).
  * MIME/content-type verification.
* Files are saved in **S3** with unique keys (`uploads/user-{id}/timestamp-uuid-filename`).
* File metadata stored in the `UploadedFile` model.
* Automatic enqueueing to **SQS** after successful upload.

### 🗂 Lebenslauf Metadata

* Each uploaded CV (Lebenslauf) can be enriched with:

  * Contact info (email, phone, LinkedIn, GitHub).
  * Address and personal details.
  * Work experience (JSON field).
* Metadata stored in `LebenslaufMetadata` linked 1:1 with `UploadedFile`.

### 🛠 Services

* **Validation**: Size, extension, duplicate checks.
* **Rate limiting**: Prevent excessive uploads per user.
* **Upload service**: Handles S3 + SQS integration.
* **Monitoring**: Logs upload metrics and system health checks.

### 🖥 User Interface

* Upload form (PDF only).
* My Documents page (list, delete documents).
* Edit metadata form.

---

## 📑 Models

* **`UploadedFile`**

  * Stores user uploads (file type, location, S3 key, upload time).
* **`LebenslaufMetadata`**

  * Stores structured metadata about a CV (name, contact info, work experience).
* **`User`**

  * Custom user model extending Django’s `AbstractUser`.

---

## 📋 Forms

* **`UploadedFileForm`**: For uploading files.
* **`LebenslaufMetadataForm`**: For editing CV metadata.

---

## 🌐 Views

* `home_page`: Landing page.
* `upload_file`: Handles file upload, validation, S3 save, SQS enqueue.
* `my_documents`: Lists user’s uploaded documents, allows delete.
* `editdocument`: Edit metadata for uploaded Lebenslauf.

---

## ☁️ AWS Integration

* **S3**:

  * Upload, download, and delete documents.
  * Automatic bucket creation if missing.
* **SQS**:

  * Sends messages with file metadata for processing pipelines.
* **Bedrock (optional)**:

  * Supports AI-based document processing (e.g., resume parsing).

---

## 🛡 Logging

* All operations use `logger_setup.py` for structured logging.
* Logs stored in `logs/{app_name}_YYYYMMDD.log`.

---

## 🚀 Getting Started

### 1️⃣ Prerequisites

* Python 3.11+
* Django 4+
* PostgreSQL/MySQL (recommended)
* AWS credentials with S3 + SQS permissions.

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure settings

Update `config.ini` (via `ConfigurationCenter`) with:

```ini
[aws_configuration]
region = eu-central-1
s3_bucketname = your-s3-bucket
sqs_queue_name = your-sqs-queue
model_provider = anthropic

[general_configuration]
max_filesize_kb = 5120
```

### 4️⃣ Run migrations

```bash
python manage.py migrate
```

### 5️⃣ Create superuser

```bash
python manage.py createsuperuser
```

### 6️⃣ Start server

```bash
python manage.py runserver
```

---

## 📌 Example Workflow

1. User logs in.
2. Uploads a **PDF Lebenslauf**.
3. File is:

   * Validated (size, extension).
   * Saved to **S3**.
   * Metadata stored in DB.
   * Metadata pushed to **SQS**.
4. User can edit extracted metadata (contact info, experience).
5. User can delete document → removed from **S3** + DB.

---

## 🧪 Future Enhancements

* A separate container will be responsible for consuming messages from Amazon SQS, performing data extraction using Anthropic’s LLM, and loading the extracted CV data into the database for normalization.  
  This component is ready and will be uploaded shortly.


## ⚖️ Horizontal Scaling

To enable horizontal expansion of the Django UI container, the service is fronted by an **Application Load Balancer (ALB)** with a dedicated **Target Group**.

- **Target Group (Instance type):**  
  Registers the ECS container instances and their dynamically mapped host ports.  
  Health checks ensure traffic is routed only to healthy tasks.

- **Application Load Balancer (ALB):**  
  Distributes incoming requests across all running ECS tasks.  
  Listeners (e.g., `HTTP :80`) forward traffic to the target group.

- **ECS Service Integration:**  
  When tasks scale in or out, ECS automatically updates the target group with the correct instance/port mappings.
