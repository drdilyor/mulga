#include "mulga.h"

#include <fcitx-utils/key.h>
#include <fcitx-utils/keysym.h>
#include <fcitx-utils/textformatflags.h>
#include <fcitx/event.h>
#include <fcitx/inputpanel.h>
#include <fcitx/text.h>
#include <fcitx/userinterface.h>

#include <string>

namespace {

// Modifiers that turn a keystroke into a shortcut rather than into text.
// Shift and Lock are absent on purpose: they are how capitals get typed, and
// Sh / O' have to fold just like sh / o'.
const fcitx::KeyStates commandModifiers{fcitx::KeyState::Ctrl,
                                        fcitx::KeyState::Alt,
                                        fcitx::KeyState::Super};

} // namespace

void MulgaState::keyEvent(fcitx::KeyEvent &event) {
    if (event.isRelease()) {
        return;
    }

    const fcitx::Key &key = event.key();

    if (key.states().testAny(commandModifiers)) {
        release();
        return;
    }

    // Backspace takes back the held character instead of reaching the client.
    // The client never saw it, so passing it through would eat the character
    // before it.
    if (key.check(FcitxKey_BackSpace) && trans_.pending() != 0) {
        trans_.clear();
        updatePreedit();
        return event.filterAndAccept();
    }

    uint32_t code = fcitx::Key::keySymToUnicode(key.sym());
    if (code == 0) {
        // Escape, Return, Tab, arrows, function keys. These have to reach the
        // client untouched, which matters rather a lot in a terminal.
        release();
        return;
    }

    mulga::Transliterator::Result result = trans_.feed(code);
    if (!result.commit.empty()) {
        ic_->commitString(result.commit);
    }
    updatePreedit();

    if (result.absorbed) {
        return event.filterAndAccept();
    }
    // An ordinary character: leave the event unaccepted and let the client
    // type it itself.
}

void MulgaState::release() {
    std::string text = trans_.flush();
    if (text.empty()) {
        return;
    }
    ic_->commitString(text);
    updatePreedit();
}

void MulgaState::forget() {
    if (trans_.pending() == 0) {
        return;
    }
    trans_.clear();
    updatePreedit();
}

void MulgaState::updatePreedit() {
    fcitx::Text preedit;
    if (uint32_t pending = trans_.pending()) {
        std::string text = mulga::encodeUtf8(pending);
        preedit.setCursor(static_cast<int>(text.size()));
        preedit.append(std::move(text), fcitx::TextFormatFlag::Underline);
    }

    fcitx::InputPanel &panel = ic_->inputPanel();
    panel.reset();
    // Clients without on-the-spot editing get the held character in fcitx's
    // own panel rather than nowhere at all.
    if (ic_->capabilityFlags().test(fcitx::CapabilityFlag::Preedit)) {
        panel.setClientPreedit(preedit);
    } else {
        panel.setPreedit(preedit);
    }
    ic_->updatePreedit();
    ic_->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
}

MulgaEngine::MulgaEngine(fcitx::Instance *instance)
    : factory_([](fcitx::InputContext &ic) { return new MulgaState(&ic); }) {
    instance->inputContextManager().registerProperty("mulgaState", &factory_);
}

void MulgaEngine::keyEvent(const fcitx::InputMethodEntry &entry,
                           fcitx::KeyEvent &keyEvent) {
    FCITX_UNUSED(entry);
    keyEvent.inputContext()->propertyFor(&factory_)->keyEvent(keyEvent);
}

void MulgaEngine::reset(const fcitx::InputMethodEntry &entry,
                        fcitx::InputContextEvent &event) {
    FCITX_UNUSED(entry);
    // Clients reset us at moments we cannot predict, and dropping the held
    // character there loses a letter the user typed -- `ming` came out as
    // `min`. Releasing is safe to repeat: once given back there is nothing
    // left to give.
    event.inputContext()->propertyFor(&factory_)->release();
}

void MulgaEngine::deactivate(const fcitx::InputMethodEntry &entry,
                             fcitx::InputContextEvent &event) {
    FCITX_UNUSED(entry);
    auto *state = event.inputContext()->propertyFor(&factory_);
    if (event.type() == fcitx::EventType::InputContextFocusOut) {
        // On focus out fcitx commits the client preedit itself before we are
        // called (instance.cpp, the ReservedFirst watcher), or the client does
        // it when it claims ClientUnfocusCommit. Either way the character has
        // already been handed over, and committing it again types it twice --
        // `ming` came out as `mingg`.
        state->forget();
        return;
    }
    // Switching input method: nobody else commits the preedit, so we do.
    state->release();
}

void MulgaEngine::invokeActionImpl(const fcitx::InputMethodEntry &entry,
                                   fcitx::InvokeActionEvent &event) {
    FCITX_UNUSED(entry);
    // The default behaviour for this -- clicking inside the preedit -- commits
    // the client preedit and then resets, and our reset commits too, which
    // doubles the character for the same reason as above. Hand it over once,
    // ourselves.
    event.inputContext()->propertyFor(&factory_)->release();
    event.filter();
}

FCITX_ADDON_FACTORY(MulgaEngineFactory);
