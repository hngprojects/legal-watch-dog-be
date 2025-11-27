import logging
import logging.config

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s %(module)s:%(lineno)d — %(message)s"

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
<<<<<<< HEAD
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
=======
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
    "formatters": {
        "default": {
            "format": LOG_FORMAT,
        }
    },
<<<<<<< HEAD
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
=======
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
<<<<<<< HEAD
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
=======
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO"},
<<<<<<< HEAD
<<<<<<< HEAD

=======
>>>>>>> fix/billing-model-cleanup
=======
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
        "app": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
<<<<<<< HEAD
<<<<<<< HEAD
        }
    },

=======
        },
    },
>>>>>>> fix/billing-model-cleanup
=======
        },
    },
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


def setup_logging():
    logging.config.dictConfig(LOG_CONFIG)
