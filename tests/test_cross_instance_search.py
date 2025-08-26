import os

from app.search.cross_instance_search import get_known_instances


def test_get_known_instances_file_not_exists():
    """Test get_known_instances when the file doesn't exist"""
    instances = get_known_instances("tests/test_data", "known_instances.txt")
    assert instances == []


def test_get_known_instances_file_exists():
    """Test get_known_instances when the file exists"""
    # Set up test data
    test_instances = [
        "https://instance1.example.com",
        "https://instance2.example.com",
        "https://instance3.example.com",
    ]

    # Create directory if needed
    os.makedirs("tests/test_data", exist_ok=True)

    # Write test instances to tests/test_data/.known_instances.txt
    with open("tests/test_data/.known_instances.txt", "w") as f:
        for instance in test_instances:
            f.write(instance + "\n")

    instances = get_known_instances("tests/test_data", ".known_instances.txt")
    assert instances == test_instances

    # Clean up
    if os.path.exists("tests/test_data/.known_instances.txt"):
        os.remove("tests/test_data/.known_instances.txt")
