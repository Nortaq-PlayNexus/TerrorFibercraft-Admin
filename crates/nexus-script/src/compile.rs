use crate::lex::{Tok, tokenize};
use crate::value::{Value, VmError};

#[derive(Debug, Clone, PartialEq)]
pub enum Op {
    // stack ops
    PushConst(Value),
    PushVar(String),
    StoreVar(String),
    Pop,
    Dup,
    // arithmetic / comparison
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Eq,
    Ne,
    Lt,
    Gt,
    Le,
    Ge,
    Not,
    // control flow
    Jump(usize),
    JumpIfFalse(usize),
    Halt,
    // function call / return
    Call(String, usize),
    Ret,
    Import(String),
    // loop guards
    LoopStart,
    LoopEnd,
    Break,
}

#[derive(Debug, Clone)]
pub struct Chunk {
    pub ops: Vec<Op>,
    pub locals: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Const(Value),
    Var(String),
    Bin(Box<Expr>, BinOp, Box<Expr>),
    Unary(UnOp, Box<Expr>),
    Call(String, Vec<Expr>),
    List(Vec<Expr>),
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum BinOp {
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Eq,
    Ne,
    Lt,
    Gt,
    Le,
    Ge,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum UnOp {
    Neg,
    Not,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    Let(String, Expr),
    Assign(String, Expr),
    ExprStmt(Expr),
    If(Expr, Vec<Stmt>, Vec<Stmt>),
    While(Expr, Vec<Stmt>),
    Repeat(u64, Vec<Stmt>),
    Break,
    Return(Option<Expr>),
    Import(String),
    Run(String, Vec<String>),
    Config(Vec<(String, Expr)>),
}

#[derive(Debug, Clone)]
pub struct Program {
    pub stmts: Vec<Stmt>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct CompileOptions {
    pub allow_run: bool,
}

impl Default for CompileOptions {
    fn default() -> Self {
        Self { allow_run: true }
    }
}

/// Recursive descent parser over the token stream.
struct Parser {
    toks: Vec<Tok>,
    pos: usize,
}

impl Parser {
    fn peek(&self) -> &Tok {
        if self.pos < self.toks.len() {
            &self.toks[self.pos]
        } else {
            &Tok::Eof
        }
    }
    fn next(&mut self) -> Tok {
        let t = self.toks[self.pos].clone();
        if self.pos < self.toks.len() - 1 {
            self.pos += 1;
        }
        t
    }
    fn expect(&mut self, t: Tok) -> Result<(), VmError> {
        let got = self.next();
        if got != t {
            return Err(VmError::Compile(format!("expected {t:?}, got {got:?}")));
        }
        Ok(())
    }
    fn eat(&mut self, t: &Tok) -> bool {
        if self.peek() == t {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    fn parse_program(&mut self) -> Result<Program, VmError> {
        let mut stmts = Vec::new();
        while *self.peek() != Tok::Eof {
            stmts.push(self.parse_stmt()?);
        }
        Ok(Program { stmts })
    }

    fn parse_stmt(&mut self) -> Result<Stmt, VmError> {
        match self.next() {
            Tok::Let => {
                let name = match self.next() {
                    Tok::Ident(n) => n,
                    other => return Err(VmError::Compile(format!("expected ident, got {other:?}"))),
                };
                self.expect(Tok::Assign)?;
                let e = self.parse_expr()?;
                Ok(Stmt::Let(name, e))
            }
            Tok::If => {
                self.eat(&Tok::LParen);
                let cond = self.parse_expr()?;
                self.eat(&Tok::RParen);
                self.expect(Tok::LBrace)?;
                let then = self.parse_block()?;
                let mut els = Vec::new();
                if self.eat(&Tok::Else) {
                    self.expect(Tok::LBrace)?;
                    els = self.parse_block()?;
                }
                Ok(Stmt::If(cond, then, els))
            }
            Tok::While => {
                self.eat(&Tok::LParen);
                let cond = self.parse_expr()?;
                self.eat(&Tok::RParen);
                self.expect(Tok::LBrace)?;
                let body = self.parse_block()?;
                Ok(Stmt::While(cond, body))
            }
            Tok::Repeat => {
                let n = match self.next() {
                    Tok::Int(i) => i.max(0) as u64,
                    other => return Err(VmError::Compile(format!("expected int, got {other:?}"))),
                };
                self.expect(Tok::LBrace)?;
                let body = self.parse_block()?;
                Ok(Stmt::Repeat(n, body))
            }
            Tok::Break => Ok(Stmt::Break),
            Tok::Return => {
                if *self.peek() == Tok::Eof {
                    Ok(Stmt::Return(None))
                } else {
                    let e = self.parse_expr()?;
                    Ok(Stmt::Return(Some(e)))
                }
            }
            Tok::Import => {
                let name = match self.next() {
                    Tok::Ident(n) => n,
                    Tok::Str(n) => n,
                    other => return Err(VmError::Compile(format!("expected import, got {other:?}"))),
                };
                Ok(Stmt::Import(name))
            }
            Tok::Run => {
                let name = match self.next() {
                    Tok::Ident(n) => n,
                    other => return Err(VmError::Compile(format!("expected run name, got {other:?}"))),
                };
                // (params...) optional
                let mut params = Vec::new();
                if self.eat(&Tok::LParen) {
                    while *self.peek() != Tok::RParen && *self.peek() != Tok::Eof {
                        if let Tok::Ident(p) = self.next() {
                            params.push(p);
                        }
                        self.eat(&Tok::Comma);
                    }
                    self.expect(Tok::RParen)?;
                }
                self.expect(Tok::LBrace)?;
                let _body = self.parse_block()?;
                Ok(Stmt::Run(name, params))
            }
            Tok::Config => {
                self.expect(Tok::LBrace)?;
                let mut kv = Vec::new();
                while *self.peek() != Tok::RBrace && *self.peek() != Tok::Eof {
                    let key = match self.next() {
                        Tok::Ident(k) => k,
                        other => return Err(VmError::Compile(format!("expected config key, got {other:?}"))),
                    };
                    if !self.eat(&Tok::Assign) {
                        self.eat(&Tok::Colon);
                    }
                    let e = self.parse_expr()?;
                    kv.push((key, e));
                    self.eat(&Tok::Comma);
                }
                self.expect(Tok::RBrace)?;
                Ok(Stmt::Config(kv))
            }
            Tok::Ident(name) => {
                // could be assignment: foo = expr
                if self.eat(&Tok::Assign) {
                    let e = self.parse_expr()?;
                    Ok(Stmt::Assign(name, e))
                } else {
                    self.pos -= 1;
                    let e = self.parse_expr()?;
                    Ok(Stmt::ExprStmt(e))
                }
            }
            other => Err(VmError::Compile(format!("unexpected token {other:?}"))),
        }
    }

    fn parse_block(&mut self) -> Result<Vec<Stmt>, VmError> {
        let mut stmts = Vec::new();
        while *self.peek() != Tok::RBrace && *self.peek() != Tok::Eof {
            stmts.push(self.parse_stmt()?);
        }
        self.expect(Tok::RBrace)?;
        Ok(stmts)
    }

    fn parse_expr(&mut self) -> Result<Expr, VmError> {
        self.parse_comparison()
    }

    fn parse_comparison(&mut self) -> Result<Expr, VmError> {
        let mut lhs = self.parse_additive()?;
        loop {
            let op = match self.peek() {
                Tok::EqEq => Some(BinOp::Eq),
                Tok::BangEq => Some(BinOp::Ne),
                Tok::Lt => Some(BinOp::Lt),
                Tok::Gt => Some(BinOp::Gt),
                Tok::LtEq => Some(BinOp::Le),
                Tok::GtEq => Some(BinOp::Ge),
                _ => None,
            };
            match op {
                Some(op) => {
                    self.next();
                    let rhs = self.parse_additive()?;
                    lhs = Expr::Bin(Box::new(lhs), op, Box::new(rhs));
                }
                None => break,
            }
        }
        Ok(lhs)
    }

    fn parse_additive(&mut self) -> Result<Expr, VmError> {
        let mut lhs = self.parse_multiplicative()?;
        loop {
            let op = match self.peek() {
                Tok::Plus => Some(BinOp::Add),
                Tok::Minus => Some(BinOp::Sub),
                _ => None,
            };
            match op {
                Some(op) => {
                    self.next();
                    let rhs = self.parse_multiplicative()?;
                    lhs = Expr::Bin(Box::new(lhs), op, Box::new(rhs));
                }
                None => break,
            }
        }
        Ok(lhs)
    }

    fn parse_multiplicative(&mut self) -> Result<Expr, VmError> {
        let mut lhs = self.parse_unary()?;
        loop {
            let op = match self.peek() {
                Tok::Star => Some(BinOp::Mul),
                Tok::Slash => Some(BinOp::Div),
                Tok::Percent => Some(BinOp::Mod),
                _ => None,
            };
            match op {
                Some(op) => {
                    self.next();
                    let rhs = self.parse_unary()?;
                    lhs = Expr::Bin(Box::new(lhs), op, Box::new(rhs));
                }
                None => break,
            }
        }
        Ok(lhs)
    }

    fn parse_unary(&mut self) -> Result<Expr, VmError> {
        match self.peek() {
            Tok::Minus => {
                self.next();
                let e = self.parse_unary()?;
                Ok(Expr::Unary(UnOp::Neg, Box::new(e)))
            }
            Tok::Bang => {
                self.next();
                let e = self.parse_unary()?;
                Ok(Expr::Unary(UnOp::Not, Box::new(e)))
            }
            _ => self.parse_primary(),
        }
    }

    fn parse_primary(&mut self) -> Result<Expr, VmError> {
        let tok = self.next();
        match tok {
            Tok::Int(i) => Ok(Expr::Const(Value::Int(i))),
            Tok::Float(f) => Ok(Expr::Const(Value::Float(f))),
            Tok::Str(s) => Ok(Expr::Const(Value::Str(s))),
            Tok::True => Ok(Expr::Const(Value::Bool(true))),
            Tok::False => Ok(Expr::Const(Value::Bool(false))),
            Tok::Nil => Ok(Expr::Const(Value::Nil)),
            Tok::Ident(name) => {
                if self.eat(&Tok::LParen) {
                    let mut args = Vec::new();
                    while *self.peek() != Tok::RParen && *self.peek() != Tok::Eof {
                        args.push(self.parse_expr()?);
                        if !self.eat(&Tok::Comma) {
                            break;
                        }
                    }
                    self.expect(Tok::RParen)?;
                    Ok(Expr::Call(name, args))
                } else {
                    Ok(Expr::Var(name))
                }
            }
            Tok::LBracket => {
                let mut items = Vec::new();
                while *self.peek() != Tok::RBracket && *self.peek() != Tok::Eof {
                    items.push(self.parse_expr()?);
                    if !self.eat(&Tok::Comma) {
                        break;
                    }
                }
                self.expect(Tok::RBracket)?;
                Ok(Expr::List(items))
            }
            Tok::LParen => {
                let e = self.parse_expr()?;
                self.expect(Tok::RParen)?;
                Ok(e)
            }
            other => Err(VmError::Compile(format!("unexpected token {other:?}"))),
        }
    }
}

/// Parse source into a Program.
pub fn parse(src: &str) -> Result<Program, VmError> {
    let toks = tokenize(src).map_err(|e| VmError::Compile(e.to_string()))?;
    let mut p = Parser { toks, pos: 0 };
    p.parse_program()
}

/// Compile (parse + static checks). `compile` returns the parsed program;
/// actual codegen happens in the VM at run time (direct AST interpretation),
/// keeping the VM simple and the sandbox limits explicit.
pub fn compile(src: &str, _opts: &CompileOptions) -> Result<Program, VmError> {
    let prog = parse(src)?;
    // static limit: no runaway repeat counts
    fn walk(stmts: &[Stmt], depth: usize) -> Result<(), VmError> {
        if depth > 64 {
            return Err(VmError::Limit("nesting too deep".into()));
        }
        for s in stmts {
            match s {
                Stmt::Repeat(n, body) => {
                    if *n > 1_000_000 {
                        return Err(VmError::Limit("repeat count too large".into()));
                    }
                    walk(body, depth + 1)?;
                }
                Stmt::While(_, body) => walk(body, depth + 1)?,
                Stmt::If(_, body, els) => {
                    walk(body, depth + 1)?;
                    walk(els, depth + 1)?;
                }
                _ => {}
            }
        }
        Ok(())
    }
    walk(&prog.stmts, 0)?;
    Ok(prog)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_simple_let() {
        let p = parse("let x = 42;").unwrap();
        assert!(matches!(p.stmts[0], Stmt::Let(_, _)));
    }

    #[test]
    fn parse_repeat_and_call() {
        let p = parse("repeat 3 { move_to(1, 2) }").unwrap();
        assert!(matches!(p.stmts[0], Stmt::Repeat(3, _)));
    }

    #[test]
    fn compile_rejects_huge_repeat() {
        let big = format!("repeat {} {{ }}\n", 1_000_001u64);
        assert!(compile(&big, &CompileOptions::default()).is_err());
    }

    #[test]
    fn parse_config_block() {
        let p = parse("config { max_runs: 5 }").unwrap();
        assert!(matches!(p.stmts[0], Stmt::Config(_)));
    }
}
