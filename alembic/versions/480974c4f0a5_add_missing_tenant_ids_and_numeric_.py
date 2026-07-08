"""add_missing_tenant_ids_and_numeric_columns

Revision ID: 480974c4f0a5
Revises: 082c179fc570
Create Date: 2026-07-08 20:36:23.432856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '480974c4f0a5'
down_revision: Union[str, Sequence[str], None] = '082c179fc570'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. additional_fields
    with op.batch_alter_table('additional_fields', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index('ix_additional_fields_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_additional_fields_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 2. booking_series
    with op.batch_alter_table('booking_series', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index('ix_booking_series_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_booking_series_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 3. invoice_lines
    with op.batch_alter_table('invoice_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('unit_price', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('amount', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.create_index('ix_invoice_lines_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_invoice_lines_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 4. invoices
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('subtotal', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('discount_total', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('tax_total', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('tip_total', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('total', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.alter_column('amount_paid', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.create_index('ix_invoices_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_invoices_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 5. payment_processor_configs
    with op.batch_alter_table('payment_processor_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index('ix_payment_processor_configs_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_payment_processor_configs_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 6. payments
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('amount', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.create_index('ix_payments_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_payments_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 7. promotion_codes
    with op.batch_alter_table('promotion_codes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('discount_value', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.drop_index('ix_promotion_codes_code')
        batch_op.create_index('ix_promotion_codes_code', ['code'], unique=False)
        batch_op.create_index('ix_promotion_codes_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_unique_constraint('uq_promotion_codes_tenant_code', ['tenant_id', 'code'])
        batch_op.create_foreign_key('fk_promotion_codes_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 8. tax_rates
    with op.batch_alter_table('tax_rates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('rate_percent', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.create_index('ix_tax_rates_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_tax_rates_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 9. tips
    with op.batch_alter_table('tips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column('amount', existing_type=sa.FLOAT(), type_=sa.Numeric(precision=10, scale=2), existing_nullable=False)
        batch_op.create_index('ix_tips_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_tips_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 10. webhooks
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index('ix_webhooks_tenant_id', ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_webhooks_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    # 10. webhooks
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_webhooks_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_webhooks_tenant_id')
        batch_op.drop_column('tenant_id')

    # 9. tips
    with op.batch_alter_table('tips', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tips_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_tips_tenant_id')
        batch_op.alter_column('amount', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 8. tax_rates
    with op.batch_alter_table('tax_rates', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tax_rates_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_tax_rates_tenant_id')
        batch_op.alter_column('rate_percent', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 7. promotion_codes
    with op.batch_alter_table('promotion_codes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_promotion_codes_tenant_id', type_='foreignkey')
        batch_op.drop_constraint('uq_promotion_codes_tenant_code', type_='unique')
        batch_op.drop_index('ix_promotion_codes_tenant_id')
        batch_op.drop_index('ix_promotion_codes_code')
        batch_op.create_index('ix_promotion_codes_code', ['code'], unique=True)
        batch_op.alter_column('discount_value', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 6. payments
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_payments_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_payments_tenant_id')
        batch_op.alter_column('amount', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 5. payment_processor_configs
    with op.batch_alter_table('payment_processor_configs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_payment_processor_configs_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_payment_processor_configs_tenant_id')
        batch_op.drop_column('tenant_id')

    # 4. invoices
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invoices_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_invoices_tenant_id')
        batch_op.alter_column('amount_paid', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('total', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('tip_total', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('tax_total', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('discount_total', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('subtotal', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 3. invoice_lines
    with op.batch_alter_table('invoice_lines', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invoice_lines_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_invoice_lines_tenant_id')
        batch_op.alter_column('amount', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.alter_column('unit_price', existing_type=sa.Numeric(precision=10, scale=2), type_=sa.FLOAT(), existing_nullable=False)
        batch_op.drop_column('tenant_id')

    # 2. booking_series
    with op.batch_alter_table('booking_series', schema=None) as batch_op:
        batch_op.drop_constraint('fk_booking_series_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_booking_series_tenant_id')
        batch_op.drop_column('tenant_id')

    # 1. additional_fields
    with op.batch_alter_table('additional_fields', schema=None) as batch_op:
        batch_op.drop_constraint('fk_additional_fields_tenant_id', type_='foreignkey')
        batch_op.drop_index('ix_additional_fields_tenant_id')
        batch_op.drop_column('tenant_id')
    # ### end Alembic commands ###
