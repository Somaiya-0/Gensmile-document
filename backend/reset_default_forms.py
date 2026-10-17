"""One-off: reset every doctor's default form to DEFAULT_FORM_FIELDS.

Fields a doctor added themselves are kept at the end, hidden, so their saved
values aren't orphaned -- the doctor can switch them back on in Form Settings.
Per-document forms (PatientDocument.form_config) are not touched.

    ./.venv/bin/python3 reset_default_forms.py
"""
import asyncio
import copy

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.doctor_form_config import DEFAULT_FORM_FIELDS, DoctorFormConfig


def reset_fields(current: list) -> list:
    core_keys = {f["key"] for f in DEFAULT_FORM_FIELDS}
    fields = copy.deepcopy(DEFAULT_FORM_FIELDS)
    custom = [f for f in current if f.get("key") not in core_keys]
    for i, f in enumerate(custom, start=len(fields) + 1):
        fields.append({**f, "order": i, "active": False, "core": False})
    return fields


async def main() -> None:
    async with AsyncSessionLocal() as db:
        configs = (await db.scalars(select(DoctorFormConfig))).all()
        for config in configs:
            config.fields = reset_fields(config.fields or [])
        await db.commit()
        print(f"Reset {len(configs)} default form(s).")


if __name__ == "__main__":
    custom = {"key": "x_ray", "label": "X-ray", "section": "Other", "active": True}
    out = reset_fields([{"key": "chief_concern", "label": "Old"}, custom])
    assert out[: len(DEFAULT_FORM_FIELDS)] == DEFAULT_FORM_FIELDS
    assert out[-1]["key"] == "x_ray" and out[-1]["active"] is False
    asyncio.run(main())
