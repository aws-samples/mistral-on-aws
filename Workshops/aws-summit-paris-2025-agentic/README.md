# AWS Paris Summit 2025 - ISV booth demo

This directory contains the code to showcase the agentic capabilities of Mistral
models within the AWS Bedrock platform.

## Getting started

This demo rely on the following external services, for which you will need to
fill in the appropriate API key in an `.env` file at the root of this directory:

- `GOOGLE_WEATHER_API_KEY` for Google's [Weather
API](https://developers.google.com/maps/documentation/weather/reference/rest).
- `GOOGLE_MAPS_GEOCODE_API_KEY` for Google Maps' [Geocoding
API](https://developers.google.com/maps/documentation/geocoding/overview).  -
`GOOGLE_ROUTES_API_KEY` for Google Maps' [Routes
API](https://developers.google.com/maps/documentation/routes).

You will also need [uv](https://github.com/astral-sh/uv) installed. 

To start the demo notebook, run:

```shell 
uv run jupyter notebook 
```

