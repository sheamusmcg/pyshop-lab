"""Pricing services. REPRESENTATIVE EXAMPLE, not a real market-data client.

Two in-process clients stand in for two versions of an external pricing
service. The platform's approved client is PricingV2. PricingLegacy is the
deprecated one that should no longer be called. Which one is approved is a
decision recorded in regression-check.yml (approved_dependencies), not in code.

Every call is written to the call_log table, so a test can prove which
service a workflow actually used. That is the evidence the regression-check
skill looks for; a text search for "legacy" in the code is not proof.

The two services return different prices for the same fund and date (legacy
lags by one day), so calling the wrong one produces wrong data, not just a log
line.
"""
from datetime import date, timedelta
from pyshop.infrastructure.models import CallLogModel, FundPriceModel, SettingModel
from sqlalchemy import select


class PricingUnavailable(Exception):
    pass


class _PricingBase:
    name = "pricing-base"

    def __init__(self, session):
        self.session = session

    def _log(self, operation, detail):
        self.session.add(CallLogModel(service=self.name, operation=operation, detail=detail))
        self.session.commit()   # the log must be durable even if the caller never commits
        # Test-only fault switch: a settings row "<service>.unavailable" = "1" makes the
        # service raise, so a scenario can exercise the fallback path deterministically.
        flag = self.session.get(SettingModel, f"{self.name}.unavailable")
        if flag is not None and flag.value == "1":
            raise PricingUnavailable(self.name)

    def _stored(self, fund_id, as_of):
        row = self.session.scalar(
            select(FundPriceModel).where(FundPriceModel.fund_id == fund_id,
                                         FundPriceModel.price_date <= as_of)
            .order_by(FundPriceModel.price_date.desc()))
        return row


class PricingV2(_PricingBase):
    """Approved pricing client. Returns the latest stored price on or before as_of."""
    name = "pricing-v2"

    def price(self, fund_id, as_of):
        self._log("price", f"fund={fund_id} as_of={as_of.isoformat()}")
        row = self._stored(fund_id, as_of)
        return row.price if row else None


class PricingLegacy(_PricingBase):
    """Deprecated pricing client. Lags one day behind: returns the price as of
    the previous day, which is why it was retired."""
    name = "pricing-legacy"

    def price(self, fund_id, as_of):
        self._log("price", f"fund={fund_id} as_of={as_of.isoformat()}")
        row = self._stored(fund_id, as_of - timedelta(days=1))
        return row.price if row else None
