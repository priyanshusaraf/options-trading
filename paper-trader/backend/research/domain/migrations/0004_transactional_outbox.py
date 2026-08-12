"""Add the research plane's delivery-only transactional outbox."""


def upgrade(connection, models) -> None:
    for model in (models.StreamHead, models.Event,
                  models.ConsumerCursor, models.ConsumerReceipt,
                  models.RetentionWatermark):
        model.__table__.create(connection, checkfirst=True)
