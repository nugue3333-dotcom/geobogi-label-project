from __future__ import annotations


class BarcodeLabelAutomationError(Exception):
    """Base exception for user-facing application errors."""


class ConfigError(BarcodeLabelAutomationError):
    """Raised when configuration is missing or invalid."""


class PrinterError(BarcodeLabelAutomationError):
    """Base exception for printer transport errors."""


class PrinterMissingConfigError(PrinterError):
    """Raised when network printer settings are incomplete."""


class PrinterInvalidIPError(PrinterError):
    """Raised when the configured network printer IP is invalid."""


class PrinterTimeoutError(PrinterError):
    """Raised when connecting to the printer times out."""


class PrinterConnectionRefusedError(PrinterError):
    """Raised when the printer host refuses the TCP connection."""


class PrinterConnectionError(PrinterError):
    """Raised for other printer connection failures."""


class PrinterHostResolutionError(PrinterConnectionError):
    """Raised when the printer host name cannot be resolved."""
