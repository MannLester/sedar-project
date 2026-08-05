"""Run ERP demonstration reconciliation after all dependencies are initialized."""


def post_init_hook(env):
    env.company.sedar_configure_demo_currency()
    env.company.sedar_ensure_erp_demo()
    return True
