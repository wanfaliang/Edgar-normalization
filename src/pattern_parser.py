"""
Pattern Parser for Natural Language Matching Patterns
=====================================================

Parses and evaluates natural language pattern expressions from CSV.

Pattern Syntax:
- Quoted strings: 'search term'
- Operators: contains, equals to, and, or, not
- Parentheses for grouping: (A or B) and C
- Square brackets for pattern blocks: [pattern]
- Pattern alternatives: [pattern1] or [pattern2]
- Position operators: position_before # target, position_after # target
- Datatype filter: [datatype = perShare], [datatype = shares]
- Min selector: min{pattern} - selects item with minimum value

Examples:
    [contains 'net income' or 'net earnings']
    [(contains 'account' or 'accounts') and (contains 'receivable')]
    [contains 'other'] and [position_before # accounts_receivables]
    min{[contains 'basic'] and [datatype = perShare]}
    [position_after # total_current_assets]
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class TokenType(Enum):
    """Token types for pattern expressions"""
    QUOTED_STRING = 'QUOTED_STRING'
    IDENTIFIER = 'IDENTIFIER'
    CONTAINS = 'CONTAINS'
    EQUALS_TO = 'EQUALS_TO'
    EQUALS = 'EQUALS'
    AND = 'AND'
    OR = 'OR'
    NOT = 'NOT'
    PLUS = 'PLUS'
    LPAREN = 'LPAREN'
    RPAREN = 'RPAREN'
    LBRACKET = 'LBRACKET'
    RBRACKET = 'RBRACKET'
    LBRACE = 'LBRACE'
    RBRACE = 'RBRACE'
    POSITION_BEFORE = 'POSITION_BEFORE'
    POSITION_AFTER = 'POSITION_AFTER'
    DATATYPE = 'DATATYPE'
    MIN = 'MIN'
    HASH = 'HASH'
    SPECIAL_INSTRUCTION = 'SPECIAL_INSTRUCTION'
    EOF = 'EOF'


class Token:
    """A token in the pattern expression"""
    def __init__(self, type: TokenType, value: Any, pos: int):
        self.type = type
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type.value}, {repr(self.value)})"


class Tokenizer:
    """Tokenize pattern expressions"""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def current_char(self) -> Optional[str]:
        """Get current character"""
        if self.pos < self.length:
            return self.text[self.pos]
        return None

    def peek(self, offset: int = 1) -> Optional[str]:
        """Peek ahead at character"""
        pos = self.pos + offset
        if pos < self.length:
            return self.text[pos]
        return None

    def advance(self):
        """Move to next character"""
        self.pos += 1

    def skip_whitespace(self):
        """Skip whitespace characters"""
        while self.current_char() and self.current_char() in ' \t\n\r':
            self.advance()

    def read_quoted_string(self) -> str:
        """Read a quoted string"""
        quote = self.current_char()  # ' or "
        self.advance()

        result = []
        while self.current_char() and self.current_char() != quote:
            result.append(self.current_char())
            self.advance()

        if self.current_char() == quote:
            self.advance()

        return ''.join(result)

    def read_word(self) -> str:
        """Read a word (alphanumeric + underscore)"""
        result = []
        while self.current_char() and (self.current_char().isalnum() or self.current_char() in '_-'):
            result.append(self.current_char())
            self.advance()
        return ''.join(result)

    def read_special_instruction(self) -> str:
        """Read text inside curly braces"""
        result = []
        depth = 1
        self.advance()  # Skip opening {

        while self.current_char() and depth > 0:
            if self.current_char() == '{':
                depth += 1
            elif self.current_char() == '}':
                depth -= 1
                if depth == 0:
                    break
            result.append(self.current_char())
            self.advance()

        if self.current_char() == '}':
            self.advance()

        return ''.join(result).strip()

    def tokenize(self) -> List[Token]:
        """Tokenize the entire pattern expression"""
        tokens = []
        last_token_type = None

        while self.pos < self.length:
            self.skip_whitespace()

            if self.pos >= self.length:
                break

            char = self.current_char()
            start_pos = self.pos

            # Single character tokens
            if char == '(':
                tokens.append(Token(TokenType.LPAREN, '(', start_pos))
                last_token_type = TokenType.LPAREN
                self.advance()
            elif char == ')':
                tokens.append(Token(TokenType.RPAREN, ')', start_pos))
                last_token_type = TokenType.RPAREN
                self.advance()
            elif char == '[':
                tokens.append(Token(TokenType.LBRACKET, '[', start_pos))
                last_token_type = TokenType.LBRACKET
                self.advance()
            elif char == ']':
                tokens.append(Token(TokenType.RBRACKET, ']', start_pos))
                last_token_type = TokenType.RBRACKET
                self.advance()
            elif char == '{':
                # If last token was MIN, treat as LBRACE, otherwise as special instruction
                if last_token_type == TokenType.MIN:
                    tokens.append(Token(TokenType.LBRACE, '{', start_pos))
                    last_token_type = TokenType.LBRACE
                    self.advance()
                else:
                    # Read special instruction
                    instruction = self.read_special_instruction()
                    tokens.append(Token(TokenType.SPECIAL_INSTRUCTION, instruction, start_pos))
                    last_token_type = TokenType.SPECIAL_INSTRUCTION
            elif char == '}':
                tokens.append(Token(TokenType.RBRACE, '}', start_pos))
                last_token_type = TokenType.RBRACE
                self.advance()
            elif char == '#':
                tokens.append(Token(TokenType.HASH, '#', start_pos))
                last_token_type = TokenType.HASH
                self.advance()
            elif char == '=':
                tokens.append(Token(TokenType.EQUALS, '=', start_pos))
                last_token_type = TokenType.EQUALS
                self.advance()
            elif char in ("'", '"'):
                # Read quoted string
                string = self.read_quoted_string()
                tokens.append(Token(TokenType.QUOTED_STRING, string, start_pos))
                last_token_type = TokenType.QUOTED_STRING
            else:
                # Read word and check for keywords
                word = self.read_word()
                word_lower = word.lower()

                if word_lower == 'contains':
                    tokens.append(Token(TokenType.CONTAINS, 'contains', start_pos))
                    last_token_type = TokenType.CONTAINS
                elif word_lower == 'equals':
                    # Check for "equals to"
                    self.skip_whitespace()
                    next_word = self.read_word()
                    if next_word.lower() == 'to':
                        tokens.append(Token(TokenType.EQUALS_TO, 'equals to', start_pos))
                        last_token_type = TokenType.EQUALS_TO
                    else:
                        # Put back the word
                        self.pos -= len(next_word)
                        tokens.append(Token(TokenType.EQUALS_TO, 'equals', start_pos))
                        last_token_type = TokenType.EQUALS_TO
                elif word_lower == 'and':
                    tokens.append(Token(TokenType.AND, 'and', start_pos))
                    last_token_type = TokenType.AND
                elif word_lower == 'or':
                    tokens.append(Token(TokenType.OR, 'or', start_pos))
                    last_token_type = TokenType.OR
                elif word_lower == 'not':
                    tokens.append(Token(TokenType.NOT, 'not', start_pos))
                    last_token_type = TokenType.NOT
                elif word_lower == 'plus':
                    tokens.append(Token(TokenType.PLUS, 'plus', start_pos))
                    last_token_type = TokenType.PLUS
                elif word_lower == 'position_before':
                    tokens.append(Token(TokenType.POSITION_BEFORE, 'position_before', start_pos))
                    last_token_type = TokenType.POSITION_BEFORE
                elif word_lower == 'position_after':
                    tokens.append(Token(TokenType.POSITION_AFTER, 'position_after', start_pos))
                    last_token_type = TokenType.POSITION_AFTER
                elif word_lower == 'datatype':
                    tokens.append(Token(TokenType.DATATYPE, 'datatype', start_pos))
                    last_token_type = TokenType.DATATYPE
                elif word_lower == 'min':
                    tokens.append(Token(TokenType.MIN, 'min', start_pos))
                    last_token_type = TokenType.MIN
                elif word:
                    # Identifier (for field names like accounts_receivables)
                    tokens.append(Token(TokenType.IDENTIFIER, word, start_pos))
                    last_token_type = TokenType.IDENTIFIER

        tokens.append(Token(TokenType.EOF, None, self.pos))
        return tokens


def normalize_text(text: str) -> str:
    """Normalize text for matching"""
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("'", "")
    text = text.replace("'", "")
    text = text.replace('-', ' ')
    text = text.replace(',', '')
    text = re.sub(r'\s+', ' ', text).strip()

    return text


class PatternEvaluator:
    """Evaluate pattern expressions"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        """Get current token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def advance(self):
        """Move to next token"""
        if self.pos < len(self.tokens) - 1:
            self.pos += 1

    def evaluate(self, label: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate the pattern against a label

        Args:
            label: Text to match against
            context: Optional context with line_num, control_lines, etc.

        Returns:
            True if pattern matches
        """
        label_norm = normalize_text(label)
        context = context or {}

        return self.parse_or_expression(label_norm, context)

    def parse_or_expression(self, label: str, context: Dict) -> bool:
        """Parse OR expressions (lowest precedence)"""
        left = self.parse_and_expression(label, context)

        while self.current_token().type == TokenType.OR:
            self.advance()
            right = self.parse_and_expression(label, context)
            left = left or right

        return left

    def parse_and_expression(self, label: str, context: Dict) -> bool:
        """Parse AND expressions"""
        left = self.parse_not_expression(label, context)

        while self.current_token().type == TokenType.AND:
            self.advance()
            right = self.parse_not_expression(label, context)
            left = left and right

        return left

    def parse_not_expression(self, label: str, context: Dict) -> bool:
        """Parse NOT expressions"""
        if self.current_token().type == TokenType.NOT:
            self.advance()
            return not self.parse_primary(label, context)

        return self.parse_primary(label, context)

    def parse_primary(self, label: str, context: Dict) -> bool:
        """Parse primary expressions"""
        token = self.current_token()

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self.advance()
            result = self.parse_or_expression(label, context)
            if self.current_token().type == TokenType.RPAREN:
                self.advance()
            return result

        # Bracket expression - treat as grouped
        if token.type == TokenType.LBRACKET:
            self.advance()
            result = self.parse_or_expression(label, context)
            if self.current_token().type == TokenType.RBRACKET:
                self.advance()
            return result

        # Min selector - strip min{} wrapper and evaluate inner pattern
        if token.type == TokenType.MIN:
            self.advance()
            if self.current_token().type == TokenType.LBRACE:
                self.advance()
                result = self.parse_or_expression(label, context)
                if self.current_token().type == TokenType.RBRACE:
                    self.advance()
                # Mark context that this should select minimum
                context['_select_min'] = True
                return result
            return False

        # Contains operator
        if token.type == TokenType.CONTAINS:
            self.advance()
            return self.parse_contains(label)

        # Equals operator
        if token.type == TokenType.EQUALS_TO:
            self.advance()
            return self.parse_equals(label)

        # Position before operator
        if token.type == TokenType.POSITION_BEFORE:
            self.advance()
            return self.parse_position_before(context)

        # Position after operator
        if token.type == TokenType.POSITION_AFTER:
            self.advance()
            return self.parse_position_after(context)

        # Datatype filter
        if token.type == TokenType.DATATYPE:
            self.advance()
            return self.parse_datatype(context)

        # Special instruction
        if token.type == TokenType.SPECIAL_INSTRUCTION:
            self.advance()
            return self.evaluate_special_instruction(token.value, context)

        # Quoted string (assume contains if no operator)
        if token.type == TokenType.QUOTED_STRING:
            self.advance()
            # Normalize the pattern string before comparison
            pattern_term = normalize_text(token.value)
            return pattern_term in label

        return False

    def parse_contains(self, label: str) -> bool:
        """Parse contains expression"""
        # Can be: contains 'text' or contains ('a' or 'b')
        token = self.current_token()

        if token.type == TokenType.LPAREN:
            # Parenthesized alternatives
            self.advance()
            result = self.parse_contains_alternatives(label)
            if self.current_token().type == TokenType.RPAREN:
                self.advance()
            return result
        elif token.type == TokenType.QUOTED_STRING:
            # Single string or OR sequence
            return self.parse_contains_alternatives(label)

        return False

    def parse_contains_alternatives(self, label: str) -> bool:
        """
        Parse alternatives in contains: 'a' or 'b' or 'c'
        Handles both: contains 'a' or 'b' AND contains 'a' or contains 'b'
        """
        results = []

        while True:
            token = self.current_token()

            if token.type == TokenType.QUOTED_STRING:
                # Normalize the pattern string before comparison
                pattern_term = normalize_text(token.value)
                results.append(pattern_term in label)
                self.advance()

                # Check for 'or'
                if self.current_token().type == TokenType.OR:
                    self.advance()

                    # Check if next is 'contains' (optional)
                    if self.current_token().type == TokenType.CONTAINS:
                        self.advance()

                    continue
                else:
                    break
            else:
                break

        return any(results) if results else False

    def parse_equals(self, label: str) -> bool:
        """Parse equals expression"""
        token = self.current_token()

        if token.type == TokenType.QUOTED_STRING:
            result = normalize_text(token.value) == label
            self.advance()

            # Check for 'or' alternatives
            while self.current_token().type == TokenType.OR:
                self.advance()

                # Check if next is 'equals to' (optional)
                if self.current_token().type == TokenType.EQUALS_TO:
                    self.advance()

                if self.current_token().type == TokenType.QUOTED_STRING:
                    result = result or (normalize_text(self.current_token().value) == label)
                    self.advance()
                else:
                    break

            return result

        return False

    def parse_position_before(self, context: Dict) -> bool:
        """
        Parse position_before # target expression

        Syntax: position_before # accounts_receivables
        Multiple targets: position_before # target1 or position_before # target2

        Context must contain:
            - line_num: Current line number
            - target_line_numbers: Dict mapping target names to line numbers
        """
        # Expect # symbol
        if self.current_token().type != TokenType.HASH:
            return False
        self.advance()

        # Get target identifier
        if self.current_token().type != TokenType.IDENTIFIER:
            return False

        target = self.current_token().value
        self.advance()

        # Check position
        if not context.get('line_num') or not context.get('target_line_numbers'):
            return True  # Permissive if context missing

        current_line = context['line_num']
        target_lines = context['target_line_numbers']

        if target in target_lines:
            return current_line < target_lines[target]

        return True  # Permissive if target not found

    def parse_position_after(self, context: Dict) -> bool:
        """
        Parse position_after # target expression

        Syntax: position_after # total_current_assets
        Multiple targets: position_after # target1 or position_after # target2

        Context must contain:
            - line_num: Current line number
            - target_line_numbers: Dict mapping target names to line numbers
        """
        # Expect # symbol
        if self.current_token().type != TokenType.HASH:
            return False
        self.advance()

        # Get target identifier
        if self.current_token().type != TokenType.IDENTIFIER:
            return False

        target = self.current_token().value
        self.advance()

        # Check position
        if not context.get('line_num') or not context.get('target_line_numbers'):
            return True  # Permissive if context missing

        current_line = context['line_num']
        target_lines = context['target_line_numbers']

        if target in target_lines:
            return current_line > target_lines[target]

        return True  # Permissive if target not found

    def parse_datatype(self, context: Dict) -> bool:
        """
        Parse datatype = value expression

        Syntax: [datatype = perShare] or [datatype = shares]

        Context must contain:
            - datatype: The item's datatype from database
        """
        # Expect = symbol
        if self.current_token().type != TokenType.EQUALS:
            return False
        self.advance()

        # Get expected datatype (can be identifier or quoted string)
        expected_datatype = None
        if self.current_token().type == TokenType.IDENTIFIER:
            expected_datatype = self.current_token().value
            self.advance()
        elif self.current_token().type == TokenType.QUOTED_STRING:
            expected_datatype = self.current_token().value
            self.advance()
        else:
            return False

        # Check datatype in context
        if not context.get('datatype'):
            return True  # Permissive if datatype not in context

        actual_datatype = context['datatype']
        return actual_datatype == expected_datatype

    def evaluate_special_instruction(self, instruction: str, context: Dict) -> bool:
        """
        Evaluate special positional instructions

        Examples:
            {position line before that of accounts_receivables or accounts_payables}
            {position line is smaller than that of X by one or two}
        """
        if not context.get('line_num'):
            return True  # Can't evaluate without line number

        line_num = context['line_num']

        # Parse "position line before that of X or Y"
        if 'position line before that of' in instruction:
            # Extract target items
            parts = instruction.split('position line before that of')
            if len(parts) > 1:
                targets_str = parts[1].strip()
                targets = [t.strip() for t in targets_str.split(' or ')]

                # Check if this line is before any of the targets
                # (requires additional context about where target items are)
                # For now, return True (permissive)
                return True

        # Parse "position line is smaller than that of X by one or two"
        if 'position line is smaller than' in instruction:
            # This requires knowing the line number of the reference item
            # For now, return True (permissive)
            return True

        return True


def parse_pattern(pattern: str, label: str, context: Optional[Dict] = None) -> bool:
    """
    Parse and evaluate a pattern expression

    Args:
        pattern: Pattern string from CSV
        label: Label to match against
        context: Optional context with line_num, control_lines, etc.

    Returns:
        True if pattern matches label
    """
    if not pattern or not isinstance(pattern, str):
        return False

    try:
        tokenizer = Tokenizer(pattern)
        tokens = tokenizer.tokenize()

        evaluator = PatternEvaluator(tokens)
        return evaluator.evaluate(label, context)
    except Exception as e:
        print(f"Error parsing pattern: {pattern}")
        print(f"Error: {e}")
        return False
