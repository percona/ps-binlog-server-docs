
def define_env(env):
    """
    This is the hook for the variables, macros and filters.
    """

    @env.macro
    def price(unit_price, no):
        "Calculate price"
        return unit_price * no
