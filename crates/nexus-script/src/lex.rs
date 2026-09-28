use thiserror::Error;

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    // literals
    Int(i64),
    Float(f64),
    Str(String),
    Ident(String),
    // keywords
    Let,
    If,
    Else,
    Repeat,
    Run,
    Import,
    Config,
    While,
    Break,
    Return,
    True,
    False,
    Nil,
    // operators & punctuation
    Plus,
    Minus,
    Star,
    Slash,
    Percent,
    Eq,
    EqEq,
    BangEq,
    Lt,
    Gt,
    LtEq,
    GtEq,
    Bang,
    Assign,   // "=" is handled as Eq with different meaning; we treat single '=' as Assign
    Dot,
    Comma,
    LParen,
    RParen,
    LBrace,
    RBrace,
    LBracket,
    RBracket,
    Arrow, // "=>"
    Colon,
    Eof,
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum LexError {
    #[error("unexpected character at {line}:{col}: '{c}'")]
    Unexpected { line: usize, col: usize, c: char },
    #[error("unterminated string at {line}:{col}")]
    UnterminatedString { line: usize, col: usize },
}

pub fn tokenize(src: &str) -> Result<Vec<Tok>, LexError> {
    let mut toks = Vec::new();
    let chars: Vec<char> = src.chars().collect();
    let mut i = 0usize;
    let mut line = 1usize;
    let mut col = 1usize;

    macro_rules! bump {
        () => {{
            let c = chars[i];
            i += 1;
            if c == '\n' {
                line += 1;
                col = 1;
            } else {
                col += 1;
            }
            c
        }};
    }

    while i < chars.len() {
        let c = chars[i];
        match c {
            ' ' | '\t' | '\r' | '\n' | ';' => {
                bump!();
            }
            '#' => {
                // comment to end of line
                while i < chars.len() && chars[i] != '\n' {
                    bump!();
                }
            }
            '0'..='9' => {
                let mut num = String::new();
                while i < chars.len() && (chars[i].is_ascii_digit() || chars[i] == '.') {
                    num.push(bump!());
                }
                if num.contains('.') {
                    toks.push(Tok::Float(num.parse().unwrap()));
                } else {
                    toks.push(Tok::Int(num.parse().unwrap()));
                }
            }
            '"' => {
                bump!();
                let mut s = String::new();
                let (l0, c0) = (line, col);
                while i < chars.len() {
                    let ch = bump!();
                    if ch == '"' {
                        break;
                    }
                    if ch == '\\' {
                        if i < chars.len() {
                            let esc = bump!();
                            s.push(match esc {
                                'n' => '\n',
                                't' => '\t',
                                '\\' => '\\',
                                '"' => '"',
                                other => other,
                            });
                        }
                    } else {
                        s.push(ch);
                    }
                }
                if i >= chars.len() && chars[i - 1] != '"' {
                    // only unterminated if we hit EOF without closing
                    if !s.ends_with('"') && i >= chars.len() {
                        return Err(LexError::UnterminatedString { line: l0, col: c0 });
                    }
                }
                toks.push(Tok::Str(s));
            }
            'a'..='z' | 'A'..='Z' | '_' => {
                let mut id = String::new();
                while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                    id.push(bump!());
                }
                toks.push(match id.as_str() {
                    "let" => Tok::Let,
                    "if" => Tok::If,
                    "else" => Tok::Else,
                    "repeat" => Tok::Repeat,
                    "run" => Tok::Run,
                    "import" => Tok::Import,
                    "config" => Tok::Config,
                    "while" => Tok::While,
                    "break" => Tok::Break,
                    "return" => Tok::Return,
                    "true" => Tok::True,
                    "false" => Tok::False,
                    "nil" => Tok::Nil,
                    _ => Tok::Ident(id),
                });
            }
            '+' => { bump!(); toks.push(Tok::Plus); }
            '-' => { bump!(); toks.push(Tok::Minus); }
            '*' => { bump!(); toks.push(Tok::Star); }
            '/' => { bump!(); toks.push(Tok::Slash); }
            '%' => { bump!(); toks.push(Tok::Percent); }
            '(' => { bump!(); toks.push(Tok::LParen); }
            ')' => { bump!(); toks.push(Tok::RParen); }
            '{' => { bump!(); toks.push(Tok::LBrace); }
            '}' => { bump!(); toks.push(Tok::RBrace); }
            '[' => { bump!(); toks.push(Tok::LBracket); }
            ']' => { bump!(); toks.push(Tok::RBracket); }
            ',' => { bump!(); toks.push(Tok::Comma); }
            ':' => { bump!(); toks.push(Tok::Colon); }
            '.' => { bump!(); toks.push(Tok::Dot); }
            '=' => {
                bump!();
                if i < chars.len() && chars[i] == '=' {
                    bump!();
                    toks.push(Tok::EqEq);
                } else if i < chars.len() && chars[i] == '>' {
                    bump!();
                    toks.push(Tok::Arrow);
                } else {
                    toks.push(Tok::Assign);
                }
            }
            '!' => {
                bump!();
                if i < chars.len() && chars[i] == '=' {
                    bump!();
                    toks.push(Tok::BangEq);
                } else {
                    toks.push(Tok::Bang);
                }
            }
            '<' => {
                bump!();
                if i < chars.len() && chars[i] == '=' {
                    bump!();
                    toks.push(Tok::LtEq);
                } else {
                    toks.push(Tok::Lt);
                }
            }
            '>' => {
                bump!();
                if i < chars.len() && chars[i] == '=' {
                    bump!();
                    toks.push(Tok::GtEq);
                } else {
                    toks.push(Tok::Gt);
                }
            }
            other => {
                return Err(LexError::Unexpected {
                    line,
                    col,
                    c: other,
                });
            }
        }
    }
    toks.push(Tok::Eof);
    Ok(toks)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenizes_literals() {
        let t = tokenize("let x = 42; if x > 3 { true }").unwrap();
        assert!(t.contains(&Tok::Let));
        assert!(t.contains(&Tok::Int(42)));
        assert!(t.contains(&Tok::Gt));
        assert!(t.contains(&Tok::True));
    }

    #[test]
    fn comments_and_whitespace() {
        let t = tokenize("# hi\nlet a = \"x\" # trailing").unwrap();
        assert!(t.contains(&Tok::Str("x".into())));
    }

    #[test]
    fn unknown_char_errors() {
        assert!(tokenize("let $ = 1").is_err());
    }
}
