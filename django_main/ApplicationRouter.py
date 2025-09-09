# ApplicationRouter.py
class ApplicationRouter:
    # Everything *not* in these apps should go to application_realm
    EXCLUDED_APP_LABELS = {"admin", "contenttypes", "auth", "accounts_app"}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.EXCLUDED_APP_LABELS:
            return None  # let AuthRouter decide
        return "application_realm"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.EXCLUDED_APP_LABELS:
            return None  # let AuthRouter decide
        return "application_realm"

    def allow_relation(self, obj1, obj2, **hints):
        db_set = {"application_realm"}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Only allow non-excluded apps to migrate on application_realm
        if app_label in self.EXCLUDED_APP_LABELS:
            return None  # defer to AuthRouter
        return db == "application_realm"
