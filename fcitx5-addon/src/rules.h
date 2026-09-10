/*
 * The alphabet reform itself: sh -> ş, ch -> ç, o' -> ö, g' -> ğ.
 *
 * Deliberately free of fcitx headers so the tests can drive exactly the same
 * state machine the input method does.
 */
#ifndef _MULGA_RULES_H_
#define _MULGA_RULES_H_

#include <cstdint>
#include <string>
#include <string_view>

namespace mulga {

// Characters that may begin a digraph, and so have to be held back until the
// next keystroke decides what they are.
bool isStarter(uint32_t c);

// Every shape the tutuq belgisi of o' / g' shows up as in practice.
bool isApostrophe(uint32_t c);

// The reformed letter for `first` + `second`, empty when the pair is not one.
std::string_view combine(uint32_t first, uint32_t second);

std::string encodeUtf8(uint32_t c);

// Keystroke-level state machine, holding at most one character.
class Transliterator {
  public:
    struct Result {
        // Text to hand the client before the current character.
        std::string commit;
        // True when the character was taken (held, or folded into a digraph);
        // false when the caller still has to emit it itself.
        bool absorbed;
    };

    Result feed(uint32_t c);

    // Gives up the held character as plain text, e.g. when focus moves away.
    std::string flush();

    // Drops the held character without emitting it.
    void clear() { pending_ = 0; }

    uint32_t pending() const { return pending_; }

  private:
    uint32_t pending_ = 0;
};

// Whole-text conversion, built on the same state machine.
std::string transliterate(std::string_view text);

} // namespace mulga

#endif // _MULGA_RULES_H_
