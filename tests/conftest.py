import pytest
from omegaconf import OmegaConf


@pytest.fixture
def config():
    return OmegaConf.create(
        {
            "family": "The Testers",
            "sender": "santa@example.com",
            "password": "pw",
            "subject": "A letter for {{ gifter }}",
            "page_url": "https://example.github.io/secret-santa/",
            "wishlist": "https://example.com/wishlist",
            "deadline": "December 1st",
            "groups": {
                "ab": [{"name": "a", "email": "a@example.com"}, {"name": "b", "email": "b@example.com"}],
                "cde": [
                    {"name": "c", "email": "c@example.com"},
                    {"name": "d", "email": "d@example.com"},
                    {"name": "ana maria", "email": "e@example.com"},
                ],
                "f": [{"name": "f", "email": "f@example.com"}],
                "gh": [{"name": "g", "email": "g@example.com"}, {"name": "h", "email": "h@example.com"}],
            },
        }
    )
