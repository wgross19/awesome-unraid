# Unraid App Factory Catalog

Community Applications catalog for Unraid AIO application templates produced by the Unraid App Factory.

This repository is bootstrapped as an empty catalog framework. It intentionally contains no copied application XML files, icons, screenshots, or app manifest entries.

## Ownership

- Source AIO repositories own Dockerfiles, runtime behavior, tests, releases, and app documentation.
- `aio-fleet` owns validation and catalog synchronization policy.
- This repository owns the published Community Applications XML, icons, screenshots, and maintainer profile.

## Catalog workflow

1. Validate the source app repository through `aio-fleet`.
2. Publish and verify the application image.
3. Synchronize the source XML and assets into this repository.
4. Review the catalog pull request.
5. Install the template through Unraid Community Applications.
