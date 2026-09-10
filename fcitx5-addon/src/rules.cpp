#include "rules.h"

namespace mulga {

namespace {

// U+02BB is the tutuq belgisi the old standard prescribed; the rest are what
// keyboards, word processors and pasted text actually produce.
constexpr uint32_t apostrophes[] = {
    0x0027, // ' APOSTROPHE
    0x0060, // ` GRAVE ACCENT
    0x00B4, // ´ ACUTE ACCENT
    0x02B9, // ʹ MODIFIER LETTER PRIME
    0x02BB, // ʻ MODIFIER LETTER TURNED COMMA
    0x02BC, // ʼ MODIFIER LETTER APOSTROPHE
    0x2018, // ' LEFT SINGLE QUOTATION MARK
    0x2019, // ' RIGHT SINGLE QUOTATION MARK
    0x2032, // ′ PRIME
};

// Decodes one character, reporting how many bytes it spanned. Malformed bytes
// come back as 0 and advance by one, so a conversion never drops input.
size_t decodeUtf8(std::string_view s, size_t i, uint32_t &out) {
    auto lead = static_cast<unsigned char>(s[i]);
    size_t len;
    uint32_t c;
    if (lead < 0x80) {
        out = lead;
        return 1;
    } else if ((lead & 0xE0) == 0xC0) {
        len = 2;
        c = lead & 0x1FU;
    } else if ((lead & 0xF0) == 0xE0) {
        len = 3;
        c = lead & 0x0FU;
    } else if ((lead & 0xF8) == 0xF0) {
        len = 4;
        c = lead & 0x07U;
    } else {
        out = 0;
        return 1;
    }
    if (i + len > s.size()) {
        out = 0;
        return 1;
    }
    for (size_t k = 1; k < len; k++) {
        auto cont = static_cast<unsigned char>(s[i + k]);
        if ((cont & 0xC0) != 0x80) {
            out = 0;
            return 1;
        }
        c = (c << 6) | (cont & 0x3FU);
    }
    out = c;
    return len;
}

} // namespace

bool isApostrophe(uint32_t c) {
    for (uint32_t a : apostrophes) {
        if (a == c) {
            return true;
        }
    }
    return false;
}

bool isStarter(uint32_t c) {
    switch (c) {
    case 's':
    case 'S':
    case 'c':
    case 'C':
    case 'o':
    case 'O':
    case 'g':
    case 'G':
        return true;
    default:
        return false;
    }
}

std::string_view combine(uint32_t first, uint32_t second) {
    // A lowercase letter followed by a capital H ("sH") is not a word anyone
    // types on purpose, so only the all-lowercase, capitalised and all-caps
    // shapes fold.
    switch (first) {
    case 's':
        return second == 'h' ? "ş" : "";
    case 'S':
        return (second == 'h' || second == 'H') ? "Ş" : "";
    case 'c':
        return second == 'h' ? "ç" : "";
    case 'C':
        return (second == 'h' || second == 'H') ? "Ç" : "";
    case 'o':
        return isApostrophe(second) ? "ö" : "";
    case 'O':
        return isApostrophe(second) ? "Ö" : "";
    case 'g':
        return isApostrophe(second) ? "ğ" : "";
    case 'G':
        return isApostrophe(second) ? "Ğ" : "";
    default:
        return "";
    }
}

std::string encodeUtf8(uint32_t c) {
    std::string out;
    if (c < 0x80) {
        out += static_cast<char>(c);
    } else if (c < 0x800) {
        out += static_cast<char>(0xC0 | (c >> 6));
        out += static_cast<char>(0x80 | (c & 0x3F));
    } else if (c < 0x10000) {
        out += static_cast<char>(0xE0 | (c >> 12));
        out += static_cast<char>(0x80 | ((c >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (c & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | (c >> 18));
        out += static_cast<char>(0x80 | ((c >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((c >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (c & 0x3F));
    }
    return out;
}

Transliterator::Result Transliterator::feed(uint32_t c) {
    if (pending_ != 0) {
        std::string_view folded = combine(pending_, c);
        if (!folded.empty()) {
            pending_ = 0;
            return {std::string(folded), true};
        }
    }

    // Whatever was held is not part of a digraph after all. Note that this is
    // what keeps `as'hob` intact: the apostrophe releases the `s`, and the `h`
    // that follows has nothing left to attach to.
    std::string prefix = flush();

    if (isStarter(c)) {
        pending_ = c;
        return {std::move(prefix), true};
    }
    return {std::move(prefix), false};
}

std::string Transliterator::flush() {
    if (pending_ == 0) {
        return {};
    }
    std::string out = encodeUtf8(pending_);
    pending_ = 0;
    return out;
}

std::string transliterate(std::string_view text) {
    Transliterator state;
    std::string out;
    size_t i = 0;
    while (i < text.size()) {
        uint32_t c = 0;
        size_t len = decodeUtf8(text, i, c);
        Transliterator::Result result = state.feed(c);
        out += result.commit;
        if (!result.absorbed) {
            // Copy the original bytes rather than re-encoding, so anything we
            // failed to decode survives untouched.
            out.append(text.substr(i, len));
        }
        i += len;
    }
    out += state.flush();
    return out;
}

} // namespace mulga
