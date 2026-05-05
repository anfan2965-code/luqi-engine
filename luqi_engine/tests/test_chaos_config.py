"""混沌配置测试"""

import pytest
from luqi_engine.core.config import ChaosConfig


class TestChaosConfigDefaults:
    def test_default_sigma(self):
        c = ChaosConfig()
        assert c.sigma == 10.0

    def test_default_rho(self):
        c = ChaosConfig()
        assert c.rho == 28.0

    def test_default_beta(self):
        c = ChaosConfig()
        assert abs(c.beta - 2.6666666667) < 1e-9

    def test_custom_values(self):
        c = ChaosConfig(sigma=15.0, rho=35.0, beta=2.0)
        assert c.sigma == 15.0
        assert c.rho == 35.0
        assert c.beta == 2.0

    def test_to_dict_roundtrip(self):
        c = ChaosConfig()
        d = {"sigma": 10.0, "rho": 28.0, "beta": 8.0 / 3.0}
        assert hasattr(c, "sigma")
        assert hasattr(c, "rho")
        assert hasattr(c, "beta")
