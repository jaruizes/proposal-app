package io.github.jaruizes.proposal.domain.model;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class MarkdownContentTest {
    @Test
    void unwrapsWholeDocumentButPreservesEmbeddedCodeBlocks() {
        var wrapped = "```markdown\n# Estrategia\n\nTexto\n\n```json\n{}\n```\n```";
        assertThat(MarkdownContent.unwrapDocument(wrapped))
                .isEqualTo("# Estrategia\n\nTexto\n\n```json\n{}\n```");
    }

    @Test
    void leavesRawMarkdownAndIncompleteOrOrdinaryCodeBlocksUntouched() {
        var raw = "# Estrategia\n\n```java\nclass Example {}\n```";
        assertThat(MarkdownContent.unwrapDocument(raw)).isEqualTo(raw);
        assertThat(MarkdownContent.unwrapDocument("```markdown\n# Estrategia\nTexto"))
                .isEqualTo("```markdown\n# Estrategia\nTexto");
        assertThat(MarkdownContent.unwrapDocument("```markdown\nplain example\n```"))
                .isEqualTo("```markdown\nplain example\n```");
    }
}
