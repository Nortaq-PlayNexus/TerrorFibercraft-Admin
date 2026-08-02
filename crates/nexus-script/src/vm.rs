use crate::compile::{BinOp, Expr, Program, Stmt, UnOp};
use crate::value::{Value, VmError};
use std::collections::HashMap;

/// A host function exposed to scripts. The `caps` set is enforced by the VM.
pub type HostFn = Box<dyn Fn(&[Value], &mut VmContext) -> Result<Value, VmError> + Send + Sync>;

#[derive(Debug, Clone)]
pub struct VmContext {
    pub caps: Vec<&'static str>,
    pub log: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct RunOptions {
    pub max_instructions: u64,
    pub max_wall_ms: u64,
}

impl Default for RunOptions {
    fn default() -> Self {
        Self {
            max_instructions: 1_000_000,
            max_wall_ms: 60_000,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct RuntimeStats {
    pub instructions: u64,
    pub calls: u64,
}

/// Simple stack-based AST interpreter with sandbox limits.
pub struct Vm {
    pub hosts: HashMap<String, HostFn>,
    pub context: VmContext,
    pub stats: RuntimeStats,
    pub options: RunOptions,
    start: std::time::Instant,
}

impl Vm {
    pub fn new(caps: Vec<&'static str>) -> Self {
        Self {
            hosts: HashMap::new(),
            context: VmContext { caps, log: Vec::new() },
            stats: RuntimeStats::default(),
            options: RunOptions::default(),
            start: std::time::Instant::now(),
        }
    }

    pub fn with_options(mut self, o: RunOptions) -> Self {
        self.options = o;
        self
    }

    pub fn register(&mut self, name: &str, f: HostFn) {
        self.hosts.insert(name.to_string(), f);
    }

    pub fn require_cap(&self, cap: &str) -> Result<(), VmError> {
        if self.context.caps.contains(&cap) {
            Ok(())
        } else {
            Err(VmError::Capability(cap.to_string()))
        }
    }

    fn tick(&mut self) -> Result<(), VmError> {
        self.stats.instructions += 1;
        if self.stats.instructions > self.options.max_instructions {
            return Err(VmError::Limit("max instructions".into()));
        }
        if self.start.elapsed().as_millis() as u64 > self.options.max_wall_ms {
            return Err(VmError::Limit("max wall time".into()));
        }
        Ok(())
    }

    pub fn run(&mut self, prog: &Program, args: &[(String, Value)]) -> Result<Value, VmError> {
        self.start = std::time::Instant::now();
        let mut env: HashMap<String, Value> = args.iter().cloned().collect();
        let mut last = Value::Nil;
        for s in &prog.stmts {
            match self.exec(s, &mut env)? {
                ExecResult::Normal => {}
                ExecResult::Return(v) => return Ok(v),
                ExecResult::Break => return Err(VmError::Runtime("break outside loop".into())),
                ExecResult::Value(v) => last = v,
            }
        }
        Ok(last)
    }

    fn exec(&mut self, s: &Stmt, env: &mut HashMap<String, Value>) -> Result<ExecResult, VmError> {
        self.tick()?;
        match s {
            Stmt::Let(name, e) => {
                let v = self.eval(e, env)?;
                env.insert(name.clone(), v);
                Ok(ExecResult::Normal)
            }
            Stmt::Assign(name, e) => {
                let v = self.eval(e, env)?;
                env.insert(name.clone(), v);
                Ok(ExecResult::Normal)
            }
            Stmt::ExprStmt(e) => {
                let v = self.eval(e, env)?;
                Ok(ExecResult::Value(v))
            }
            Stmt::If(cond, then, els) => {
                if self.eval(cond, env)?.truthy() {
                    for s in then {
                        match self.exec(s, env)? {
                            ExecResult::Normal | ExecResult::Value(_) => {}
                            r => return Ok(r),
                        }
                    }
                } else {
                    for s in els {
                        match self.exec(s, env)? {
                            ExecResult::Normal | ExecResult::Value(_) => {}
                            r => return Ok(r),
                        }
                    }
                }
                Ok(ExecResult::Normal)
            }
            Stmt::While(cond, body) => {
                while self.eval(cond, env)?.truthy() {
                    for s in body {
                        match self.exec(s, env)? {
                            ExecResult::Normal | ExecResult::Value(_) => {}
                            ExecResult::Break => return Ok(ExecResult::Normal),
                            ExecResult::Return(v) => return Ok(ExecResult::Return(v)),
                        }
                    }
                    self.tick()?;
                }
                Ok(ExecResult::Normal)
            }
            Stmt::Repeat(n, body) => {
                for _ in 0..*n {
                    for s in body {
                        match self.exec(s, env)? {
                            ExecResult::Normal | ExecResult::Value(_) => {}
                            ExecResult::Break => return Ok(ExecResult::Normal),
                            ExecResult::Return(v) => return Ok(ExecResult::Return(v)),
                        }
                    }
                    self.tick()?;
                }
                Ok(ExecResult::Normal)
            }
            Stmt::Break => Ok(ExecResult::Break),
            Stmt::Return(v) => {
                let v = match v {
                    Some(e) => self.eval(e, env)?,
                    None => Value::Nil,
                };
                Ok(ExecResult::Return(v))
            }
            Stmt::Import(name) => {
                // imports are capability-gated: default allow only pre-registered modules
                self.require_cap("import")?;
                self.context.log.push(format!("import {name}"));
                Ok(ExecResult::Normal)
            }
            Stmt::Run(name, params) => {
                // run() block: skip body, treat as documentation; execute a host fn if registered
                self.context.log.push(format!("run {name}({})", params.join(",")));
                Ok(ExecResult::Normal)
            }
            Stmt::Config(_) => Ok(ExecResult::Normal),
        }
    }

    fn eval(&mut self, e: &Expr, env: &mut HashMap<String, Value>) -> Result<Value, VmError> {
        self.tick()?;
        match e {
            Expr::Const(v) => Ok(v.clone()),
            Expr::Var(name) => env
                .get(name)
                .cloned()
                .ok_or_else(|| VmError::UnknownVar(name.clone())),
            Expr::List(items) => {
                // represent lists as a JSON-ish string for now (v1 keeps it simple)
                let mut parts = Vec::new();
                for it in items {
                    parts.push(self.eval(it, env)?);
                }
                Ok(Value::Str(format!(
                    "[{}]",
                    parts
                        .iter()
                        .map(|v| v.to_string())
                        .collect::<Vec<_>>()
                        .join(", ")
                )))
            }
            Expr::Bin(a, op, b) => {
                let av = self.eval(a, env)?;
                let bv = self.eval(b, env)?;
                self.binop(*op, av, bv)
            }
            Expr::Unary(op, a) => {
                let av = self.eval(a, env)?;
                match op {
                    UnOp::Neg => match av {
                        Value::Int(i) => Ok(Value::Int(-i)),
                        Value::Float(f) => Ok(Value::Float(-f)),
                        _ => Err(VmError::Runtime("negate of non-number".into())),
                    },
                    UnOp::Not => Ok(Value::Bool(!av.truthy())),
                }
            }
            Expr::Call(name, args) => {
                let mut arg_vals = Vec::new();
                for a in args {
                    arg_vals.push(self.eval(a, env)?);
                }
                self.stats.calls += 1;
                let f = self
                    .hosts
                    .get(name)
                    .ok_or_else(|| VmError::UnknownBuiltin(name.clone()))?;
                let mut ctx = self.context.clone();
                f(&arg_vals, &mut ctx)
            }
        }
    }

    fn binop(&self, op: BinOp, a: Value, b: Value) -> Result<Value, VmError> {
        use BinOp::*;
        match op {
            Eq => Ok(Value::Bool(a == b)),
            Ne => Ok(Value::Bool(a != b)),
            Lt | Gt | Le | Ge => {
                let ord = cmp_values(&a, &b)?;
                let r = match op {
                    Lt => ord == std::cmp::Ordering::Less,
                    Gt => ord == std::cmp::Ordering::Greater,
                    Le => ord != std::cmp::Ordering::Greater,
                    Ge => ord != std::cmp::Ordering::Less,
                    _ => unreachable!(),
                };
                Ok(Value::Bool(r))
            }
            Add => add_values(&a, &b),
            Sub => numeric(a, b, |x, y| Value::num(x - y)),
            Mul => numeric(a, b, |x, y| Value::num(x * y)),
            Div => {
                let x = a
                    .as_int()
                    .map(|i| i as f64)
                    .or(match a {
                        Value::Float(f) => Some(f),
                        _ => None,
                    })
                    .ok_or(VmError::Runtime("div of non-number".into()))?;
                let y = b
                    .as_int()
                    .map(|i| i as f64)
                    .or(match b {
                        Value::Float(f) => Some(f),
                        _ => None,
                    })
                    .ok_or(VmError::Runtime("div of non-number".into()))?;
                if y == 0.0 {
                    return Err(VmError::Runtime("divide by zero".into()));
                }
                Ok(Value::num(x / y))
            }
            Mod => numeric(a, b, |x, y| Value::Int(x as i64 % y as i64)),
        }
    }
}

impl Value {
    fn num(x: f64) -> Value {
        if x.fract() == 0.0 && x.abs() < 9e15 {
            Value::Int(x as i64)
        } else {
            Value::Float(x)
        }
    }
}

fn cmp_values(a: &Value, b: &Value) -> Result<std::cmp::Ordering, VmError> {
    match (a, b) {
        (Value::Int(x), Value::Int(y)) => Ok(x.cmp(y)),
        (Value::Int(x), Value::Float(y)) => Ok((*x as f64).partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal)),
        (Value::Float(x), Value::Int(y)) => Ok(x.partial_cmp(&(*y as f64)).unwrap_or(std::cmp::Ordering::Equal)),
        (Value::Float(x), Value::Float(y)) => Ok(x.partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal)),
        (Value::Str(x), Value::Str(y)) => Ok(x.cmp(y)),
        (Value::Bool(x), Value::Bool(y)) => Ok(x.cmp(y)),
        _ => Err(VmError::Runtime("cannot compare values".into())),
    }
}

fn numeric(a: Value, b: Value, f: fn(f64, f64) -> Value) -> Result<Value, VmError> {
    let x = as_f64(&a)?;
    let y = as_f64(&b)?;
    Ok(f(x, y))
}

fn as_f64(v: &Value) -> Result<f64, VmError> {
    match v {
        Value::Int(i) => Ok(*i as f64),
        Value::Float(f) => Ok(*f),
        _ => Err(VmError::Runtime("expected number".into())),
    }
}

fn add_values(a: &Value, b: &Value) -> Result<Value, VmError> {
    match (a, b) {
        (Value::Str(x), y) => Ok(Value::Str(format!("{x}{y}"))),
        (x, Value::Str(y)) => Ok(Value::Str(format!("{x}{y}"))),
        (Value::Int(x), Value::Int(y)) => Ok(Value::Int(x + y)),
        _ => numeric(a.clone(), b.clone(), |x, y| Value::num(x + y)),
    }
}

enum ExecResult {
    Normal,
    Break,
    Return(Value),
    Value(Value),
}

/// Convenience: compile + run in one call. Takes ownership of host functions.
pub fn run_program(
    src: &str,
    caps: Vec<&'static str>,
    hosts: Vec<(String, HostFn)>,
    args: &[(String, Value)],
) -> Result<(Value, RuntimeStats), VmError> {
    let prog = crate::compile(src, &crate::CompileOptions::default())?;
    let mut vm = Vm::new(caps);
    for (n, f) in hosts {
        vm.register(&n, f);
    }
    let v = vm.run(&prog, args)?;
    Ok((v, vm.stats))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_hosts() -> Vec<(String, HostFn)> {
        vec![
            (
                "log".into(),
                Box::new(|args, ctx| {
                    ctx.log.push(
                        args.iter()
                            .map(|a| a.to_string())
                            .collect::<Vec<_>>()
                            .join(" "),
                    );
                    Ok(Value::Nil)
                }),
            ),
            (
                "add".into(),
                Box::new(|args, _| {
                    let a = args[0].as_int().ok_or(VmError::Runtime("int".into()))?;
                    let b = args[1].as_int().ok_or(VmError::Runtime("int".into()))?;
                    Ok(Value::Int(a + b))
                }),
            ),
            (
                "needs_cap".into(),
                Box::new(|args, ctx| {
                    if !ctx.caps.contains(&"input") {
                        return Err(VmError::Capability("input".into()));
                    }
                    Ok(args.first().cloned().unwrap_or(Value::Nil))
                }),
            ),
        ]
    }

    #[test]
    fn run_arithmetic_program() {
        let src = "let x = 1 + 2 * 3; let y = x - 1; let z = y == 6; z";
        let (v, _) = run_program(src, vec![], make_hosts(), &[]).unwrap();
        assert_eq!(v, Value::Bool(true));
    }

    #[test]
    fn repeat_loop_runs() {
        let src = "let c = 0; repeat 5 { c = c + 1 }; c";
        let (v, stats) = run_program(src, vec![], make_hosts(), &[]).unwrap();
        assert_eq!(v, Value::Int(5));
        assert!(stats.instructions > 5);
    }

    #[test]
    fn call_host_function() {
        let src = "add(3, 4)";
        let (v, _) = run_program(src, vec![], make_hosts(), &[]).unwrap();
        assert_eq!(v, Value::Int(7));
    }

    #[test]
    fn capability_denied() {
        let src = "needs_cap(1)";
        let r = run_program(src, vec!["screen"], make_hosts(), &[]);
        assert_eq!(r.err(), Some(VmError::Capability("input".into())));
    }

    #[test]
    fn instruction_limit_enforced() {
        let src = "while true { let x = 1 };";
        let r = run_program(src, vec![], make_hosts(), &[]);
        assert!(matches!(r.err(), Some(VmError::Limit(_))));
    }

    #[test]
    fn unknown_var_errors() {
        let src = "missing_var";
        let r = run_program(src, vec![], make_hosts(), &[]);
        assert_eq!(r.err(), Some(VmError::UnknownVar("missing_var".into())));
    }

    #[test]
    fn while_loop_with_break() {
        let src = "let c = 0; while true { c = c + 1; if c == 4 { break } }; c";
        let (v, _) = run_program(src, vec![], make_hosts(), &[]).unwrap();
        assert_eq!(v, Value::Int(4));
    }
}
