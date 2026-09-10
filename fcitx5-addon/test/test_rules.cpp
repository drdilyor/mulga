#include "rules.h"

#include <cstdio>
#include <string>
#include <string_view>
#include <vector>

namespace {

int failures = 0;

void check(std::string_view what, const std::string &got,
           const std::string &want) {
    if (got == want) {
        return;
    }
    failures++;
    std::printf("FAIL %.*s\n  got  %s\n  want %s\n",
                static_cast<int>(what.size()), what.data(), got.c_str(),
                want.c_str());
}

// Replays a string one character at a time the way the input method does, so
// the tests cover the held-character path and not just the batch converter.
std::string type(const std::vector<uint32_t> &keys) {
    mulga::Transliterator state;
    std::string out;
    for (uint32_t key : keys) {
        mulga::Transliterator::Result result = state.feed(key);
        out += result.commit;
        if (!result.absorbed) {
            out += mulga::encodeUtf8(key);
        }
    }
    out += state.flush();
    return out;
}

} // namespace

int main() {
    struct Case {
        std::string in;
        std::string want;
    };

    const std::vector<Case> cases = {
        // The four replacements.
        {"shahar", "şahar"},
        {"choy", "çoy"},
        {"o'zbek", "özbek"},
        {"g'alaba", "ǧalaba"},

        // Case follows the first letter of the digraph.
        {"Shahar", "Şahar"},
        {"SHAHAR", "ŞAHAR"},
        {"Choy", "Çoy"},
        {"CHOY", "ÇOY"},
        {"O'zbekiston", "Özbekiston"},
        {"G'ALABA", "ǦALABA"},

        // A lowercase letter followed by a capital H is not a digraph.
        {"sHahar", "sHahar"},

        // Every apostrophe shape people actually end up with.
        {"oʻzbek", "özbek"},   // U+02BB, the prescribed tutuq belgisi
        {"o’zbek", "özbek"},   // U+2019, from word processors
        {"gʼalaba", "ǧalaba"}, // U+02BC
        {"g`alaba", "ǧalaba"}, // backtick

        // The apostrophe separates s from h, so as'hob keeps its letters.
        {"as'hob", "as'hob"},
        {"Isʼhoq", "Isʼhoq"},

        // ng is left alone, and so is a trailing letter that could have begun
        // a digraph.
        {"ming", "ming"},
        {"o", "o"},
        {"s", "s"},
        {"tosh", "toş"},

        // Several digraphs in one word.
        {"ishchi", "işçi"},
        {"o'qish", "öqiş"},
        {"g'isht", "ǧişt"},
        {"cho'chish", "çöçiş"},

        // Text that has already been converted is left alone.
        {"özbek", "özbek"},
        {"", ""},

        // Known limitation: borrowings spelled with a literal sh or ch fold
        // too. Pinned here so a change to it is a deliberate one.
        {"school", "sçool"},
    };

    for (const Case &c : cases) {
        check(c.in, mulga::transliterate(c.in), c.want);
    }

    // The keystroke path must agree with the batch converter.
    check("typed o'zbek", type({'o', '\'', 'z', 'b', 'e', 'k'}), "özbek");
    check("typed ishchi", type({'i', 's', 'h', 'c', 'h', 'i'}), "işçi");
    check("typed trailing g", type({'g'}), "g");

    // Backspace takes back a held character rather than the one before it.
    {
        mulga::Transliterator state;
        std::string out;
        out += state.feed('o').commit; // 'o' is held, nothing committed yet
        state.clear();                 // backspace
        out += state.flush();
        check("backspace drops held character", out, "");
    }

    // Focus leaving mid-digraph hands the held character over as plain text.
    {
        mulga::Transliterator state;
        std::string out;
        out += state.feed('t').absorbed ? std::string() : std::string("t");
        out += state.feed('o').commit;
        out += state.flush(); // focus out
        check("focus out releases held character", out, "to");
    }

    if (failures != 0) {
        std::printf("%d failure(s)\n", failures);
        return 1;
    }
    std::printf("all rules tests passed\n");
    return 0;
}
