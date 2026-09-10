#ifndef _MULGA_MULGA_H_
#define _MULGA_MULGA_H_

#include "rules.h"

#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextproperty.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/instance.h>

// One per input context: the character we are holding belongs to the client
// being typed into, not to the engine.
class MulgaState : public fcitx::InputContextProperty {
  public:
    explicit MulgaState(fcitx::InputContext *ic) : ic_(ic) {}

    void keyEvent(fcitx::KeyEvent &keyEvent);

    // Hands the held character to the client. The character is the user's
    // text, only borrowed until the next keystroke decides what it is, so
    // every way the borrow can end gives it back rather than dropping it.
    void release();

    // Lets go of the held character without committing it, for the paths where
    // fcitx has already committed our preedit on our behalf.
    void forget();

  private:
    void updatePreedit();

    fcitx::InputContext *ic_;
    mulga::Transliterator trans_;
};

class MulgaEngine : public fcitx::InputMethodEngineV3 {
  public:
    explicit MulgaEngine(fcitx::Instance *instance);

    void keyEvent(const fcitx::InputMethodEntry &entry,
                  fcitx::KeyEvent &keyEvent) override;
    void reset(const fcitx::InputMethodEntry &entry,
               fcitx::InputContextEvent &event) override;
    void deactivate(const fcitx::InputMethodEntry &entry,
                    fcitx::InputContextEvent &event) override;
    void invokeActionImpl(const fcitx::InputMethodEntry &entry,
                          fcitx::InvokeActionEvent &event) override;

  private:
    fcitx::FactoryFor<MulgaState> factory_;
};

class MulgaEngineFactory : public fcitx::AddonFactory {
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new MulgaEngine(manager->instance());
    }
};

#endif // _MULGA_MULGA_H_
