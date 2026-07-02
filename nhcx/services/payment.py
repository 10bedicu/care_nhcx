from decimal import Decimal

from care.emr.models.account import Account
from care.emr.models.payment_reconciliation import (
    PaymentReconciliation as EMRPaymentReconciliation,
)
from care.emr.resources.payment_reconciliation.spec import (
    PaymentReconciliationIssuerTypeOptions,
    PaymentReconciliationKindOptions,
    PaymentReconciliationOutcomeOptions,
    PaymentReconciliationPaymentMethodOptions,
    PaymentReconciliationStatusOptions,
    PaymentReconciliationTypeOptions,
)


def resolve_account(claim) -> Account | None:
    account = None
    if getattr(claim, "account", None):
        account = claim.account
    if account is None and claim.encounter:
        account = Account.objects.filter(primary_encounter=claim.encounter).first()
    if account is None:
        account = (
            Account.objects.filter(
                patient=claim.patient,
                facility=claim.provider.facility,
            )
            .order_by("-created_date")
            .first()
        )
    return account


def _notice_amount(payment_notice) -> Decimal:
    return Decimal(str((payment_notice.payment_amount or {}).get("value") or 0))


def create_draft_payment_reconciliation(
    claim, payment_notice
) -> EMRPaymentReconciliation | None:
    account = resolve_account(claim)
    if account is None:
        return None

    amount = _notice_amount(payment_notice)
    return EMRPaymentReconciliation.objects.create(
        facility=claim.provider.facility,
        account=account,
        reconciliation_type=PaymentReconciliationTypeOptions.payment.value,
        status=PaymentReconciliationStatusOptions.draft.value,
        kind=PaymentReconciliationKindOptions.online.value,
        issuer_type=PaymentReconciliationIssuerTypeOptions.insurer.value,
        outcome=PaymentReconciliationOutcomeOptions.queued.value,
        disposition=payment_notice.disposition,
        payment_datetime=payment_notice.payment_date,
        method=PaymentReconciliationPaymentMethodOptions.ddpo.value,
        tendered_amount=amount,
        returned_amount=Decimal("0"),
        amount=amount,
    )


def complete_payment_for_notice(payment_notice) -> EMRPaymentReconciliation:
    reconciliation = payment_notice.payment_reconciliation
    if reconciliation is not None:
        reconciliation.status = PaymentReconciliationStatusOptions.active.value
        reconciliation.outcome = PaymentReconciliationOutcomeOptions.complete.value
        reconciliation.payment_datetime = payment_notice.payment_date
        reconciliation.save(
            update_fields=[
                "status",
                "outcome",
                "payment_datetime",
                "modified_date",
            ]
        )
        return reconciliation

    claim = payment_notice.claim
    account = resolve_account(claim)
    if account is None:
        msg = "No billing account found for this claim; cannot record payment."
        raise ValueError(msg)

    amount = _notice_amount(payment_notice)
    return EMRPaymentReconciliation.objects.create(
        facility=claim.provider.facility,
        account=account,
        reconciliation_type=PaymentReconciliationTypeOptions.payment.value,
        status=PaymentReconciliationStatusOptions.active.value,
        kind=PaymentReconciliationKindOptions.online.value,
        issuer_type=PaymentReconciliationIssuerTypeOptions.insurer.value,
        outcome=PaymentReconciliationOutcomeOptions.complete.value,
        disposition=payment_notice.disposition,
        payment_datetime=payment_notice.payment_date,
        method=PaymentReconciliationPaymentMethodOptions.ddpo.value,
        tendered_amount=amount,
        returned_amount=Decimal("0"),
        amount=amount,
    )
