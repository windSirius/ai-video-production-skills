#!/usr/bin/env python3
from audit_similarity import score


assert score("槲寄生计划", "胡寄生计划", {"胡寄生": "槲寄生"}) == 1.0
assert score("我们继续往下看", "我们继续往下看", {}) == 1.0
assert score("完整的一句话", "完全无关", {}) < 0.9
print("PASS")
