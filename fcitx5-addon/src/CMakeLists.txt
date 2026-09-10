# Named so it produces mulga.so rather than libmulga.so, which is what fcitx
# looks for given Library=mulga in the addon config.
add_library(mulga SHARED mulga.cpp rules.cpp)
target_link_libraries(mulga PRIVATE Fcitx5::Core)
set_target_properties(mulga PROPERTIES PREFIX "")
install(TARGETS mulga DESTINATION "${FCITX_INSTALL_LIBDIR}/fcitx5")

# Addon registration, via configure_file so PROJECT_VERSION lands in it.
configure_file(mulga-addon.conf.in mulga-addon.conf)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/mulga-addon.conf" RENAME mulga.conf
        DESTINATION "${FCITX_INSTALL_PKGDATADIR}/addon")

# Input method registration.
install(FILES "mulga.conf" DESTINATION "${FCITX_INSTALL_PKGDATADIR}/inputmethod")
