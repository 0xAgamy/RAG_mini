## Run Alembic Migrations

### Configurations

```bash
cp alembic.ini.example alembic.ini
```

- Update `alembic.ini` with your database credentials (`sqlalchemy.url`)

### (Optional) create new migration
```bash
alembic revision --autogenerate -m "Add..."
``` 

### Upgrade database
```bash
alembic upgrade head
```