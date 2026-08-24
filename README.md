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

- Available templates: 3

### Available Templates (3)

- **[fastcrw-aio](fastcrw-aio.xml)**
- **[gbrain-aio](gbrain-aio.xml)**
- **[honcho-aio](honcho-aio.xml)**

## Published Image Packages

- Published image packages: 3

| Image | Purpose |
|---|---|
| [`dub19/fastcrw-aio`](https://hub.docker.com/r/dub19/fastcrw-aio) | FastCRW search and scrape backend |
| [`dub19/gbrain-aio`](https://hub.docker.com/r/dub19/gbrain-aio) | GBrain knowledge service |
| [`dub19/honcho-aio`](https://hub.docker.com/r/dub19/honcho-aio) | Honcho memory service |

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=wgross19/awesome-unraid,wgross19/fastcrw-aio,wgross19/gbrain-aio,wgross19/honcho-aio&type=Date)](https://star-history.com/#wgross19/awesome-unraid&wgross19/fastcrw-aio&wgross19/gbrain-aio&wgross19/honcho-aio&Date)
