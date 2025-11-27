import logging
import logging.config

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s %(module)s:%(lineno)d — %(message)s"

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
    "formatters": {
        "default": {
            "format": LOG_FORMAT,
        }
    },
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO"},
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
        "app": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
<<<<<<< HEAD
        }
    },

=======
        },
    },
>>>>>>> fix/billing-model-cleanup
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


def setup_logging():
    logging.config.dictConfig(LOG_CONFIG)
