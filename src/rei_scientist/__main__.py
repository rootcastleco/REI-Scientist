"""Allow `python -m rei_scientist` without installation entrypoint."""
from .cli import main
raise SystemExit(main())
