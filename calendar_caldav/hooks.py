def post_init_hook(env):
    env.cr.execute(
        "UPDATE calendar_event SET uuid = gen_random_uuid()::text WHERE uuid IS NULL"
    )
