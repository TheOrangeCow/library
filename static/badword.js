/**
 * Profanity / content moderation filter list
 *
 * This list is used ONLY for detecting and filtering inappropriate or harmful language
 * in user-generated content (e.g. chat messages, usernames, comments).
 *
 * Purpose:
 * - Prevent harassment, abuse, and offensive content in the application
 * - Improve safety and user experience in public or shared environments
 *
 * Important notes:
 * - This list is NOT intended for offensive use or display
 * - Words are included solely for detection/matching logic
 * - Some entries include variations and obfuscations to catch bypass attempts
 * - This is not exhaustive and may be adjusted over time
 */

const badword_list = [
    // Common profanity (general swear words)
    "fuck", "fucking", "fucker", "motherfucker",
    "shit", "shitty", "bullshit",
    "bitch", "bitches",
    "ass", "asshole",
    "bastard",
    "damn",
    "hell",
    "crap",
    "dick", "dickhead",
    "cock",
    "pussy",
    "cunt",
    "twat",
    "wanker",
    "slut",
    "whore",

    // Insults / harassment terms
    "idiot",
    "stupid",
    "dumb",
    "moron",
    "retard",
    "loser",
    "clown",
    "imbecile",
    "dipshit",
    "jackass",
    "prick",
    "scumbag",
    "trash",
    "pathetic",
    "noob",

    // Hate speech / highly sensitive terms (included ONLY for detection/filtering)
    // These are not endorsed in any way and are included solely to prevent their use
    "niga",
    "nigga",
    "nigger",
    "fag",
    "faggot",
    "gaylord",
    "kys",

    // Obfuscations / bypass attempts (to catch intentionally masked profanity)
    "fk",
    "fck",
    "fucc",
    "fuuck",
    "sh1t",
    "b1tch",
    "a55hole",
    "n1gga",
    "f4g"
];