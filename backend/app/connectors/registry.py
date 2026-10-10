from app.connectors.google_ads import GoogleAdsConnector
from app.connectors.google_analytics import GoogleAnalyticsConnector
from app.connectors.mongo import MongoConnector
from app.connectors.postgres import PostgresConnector
from app.connectors.spreadsheet import SpreadsheetConnector
from app.errors import ConnectorError

CONNECTORS = {
    "postgresql": PostgresConnector(),
    "mongodb": MongoConnector(),
    "spreadsheet": SpreadsheetConnector(),
    "google_ads": GoogleAdsConnector(),
    "google_analytics": GoogleAnalyticsConnector(),
}


def get_connector(source_type: str):
    try:
        return CONNECTORS[source_type]
    except KeyError as exc:
        raise ConnectorError("Unsupported data source.") from exc
