def post_init_hook(env):
    env.company.sedar_ensure_ais_demo()
    return True
