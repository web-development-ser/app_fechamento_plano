import os

from app import create_app
from app.db import apply_migrations, connect

app = create_app()

if __name__ == "__main__":
    # aplica migrations pendentes (não destrutivo), igual ao entrypoint do Docker
    with connect(app.config["DATABASE_URL"]) as conn:
        novas = apply_migrations(conn)
    if novas:
        print("Migrations aplicadas:", ", ".join(novas))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")), debug=app.config.get("DEBUG", False))
