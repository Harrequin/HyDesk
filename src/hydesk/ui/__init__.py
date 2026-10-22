"""Presentation layer (PySide6).

Views talk only to the application services via an ``AppContext``; they
contain no SQL and no business logic. Every service call that can fail is
funnelled through ``common.errors`` so a ``HyDeskError`` becomes a friendly
message rather than a crash.
"""
