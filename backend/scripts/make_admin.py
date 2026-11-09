"""Grant admin rights: python -m scripts.make_admin user@example.com  (run from the backend directory)."""
import sys

from app.core.database import SessionLocal
from app.models import User


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=sys.argv[1].lower()).first()
        if user is None:
            print("No user with that email.")
            return 1
        user.is_admin = True
        db.commit()
        print(f"{user.email} is now an administrator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
