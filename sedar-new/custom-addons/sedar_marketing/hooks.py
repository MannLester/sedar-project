"""Install-time reconciliation for the Marketing workspace."""


def post_init_hook(env):
    env.company.sedar_ensure_marketing_workspace()
    return True
