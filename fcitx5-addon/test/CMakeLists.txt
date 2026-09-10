# Links rules.cpp directly: the tests deliberately do not need fcitx running.
add_executable(test-rules test_rules.cpp ../src/rules.cpp)
target_include_directories(test-rules PRIVATE ../src)
add_test(NAME rules COMMAND test-rules)
