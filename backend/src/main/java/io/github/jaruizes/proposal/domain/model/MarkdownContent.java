package io.github.jaruizes.proposal.domain.model;

public final class MarkdownContent {
    private MarkdownContent() {}

    /** Unwrap a complete Markdown document that an LLM returned as one fenced code block. */
    public static String unwrapDocument(String raw) {
        if (raw == null) return null;
        var content = raw.trim();
        var opening = content.indexOf('\n');
        if (opening < 0 || !content.endsWith("\n```")) return raw;
        var language = content.substring(0, opening).trim();
        if (!language.equalsIgnoreCase("```markdown") && !language.equalsIgnoreCase("```md")
                && !language.equals("```")) return raw;
        var document = content.substring(opening + 1, content.length() - 4).trim();
        return document.startsWith("# ") ? document : raw;
    }
}
