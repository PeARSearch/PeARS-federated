# Tests for PeARS-federated

This directory contains tests for the PeARS-federated application.

## Running Tests

To run all tests:

```bash
pytest
```

To run tests with verbose output:

```bash
pytest -v
```

To run specific tests:

```bash
pytest tests/test_cross_instance_search.py
```

## Docker Testing

To run tests in the Docker environment:

```bash
docker build -t pears-test -f deployment/Dockerfile .
docker run pears-test pytest -v
```

## Test Coverage

To run tests with coverage:

```bash
pytest --cov=app
```

Make sure to install pytest-cov if you want to run coverage:

```bash
pip install pytest-cov
``` 