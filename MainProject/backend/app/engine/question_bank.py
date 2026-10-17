"""Curated topic library and seed question bank.

The bank serves three purposes:
  1. Grounding: the adaptive engine picks *topics* and *difficulty* from here, and the LLM is asked
     to write questions within those constraints.
  2. Rubrics: every bank question carries key concepts (with synonym patterns) that are used to
     evaluate answers in demo mode and handed to the LLM as an evaluation rubric.
  3. Fallback: when the LLM is unavailable or returns something invalid, questions come from here.

Concept tuples are (label, "pattern|pattern|..."); patterns are case-insensitive regexes matched
against the candidate's answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Concept:
    label: str
    patterns: tuple[str, ...]

    def matches(self, text: str) -> bool:
        return any(re.search(p, text, flags=re.IGNORECASE) for p in self.patterns)


@dataclass(frozen=True)
class BankQuestion:
    id: str
    topic: str
    level: int  # 1 beginner, 2 intermediate, 3 advanced
    text: str
    concepts: tuple[Concept, ...]
    hint: str
    followups: tuple[str, ...] = ()


@dataclass
class Topic:
    id: str
    name: str
    category: str  # technical | hr | project | coding
    keywords: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    questions: list[BankQuestion] = field(default_factory=list)


def _split_top(pats: str) -> list[str]:
    """Split on '|' only at the top level, so groups like (read|fetch) stay intact."""
    parts, depth, cur, esc = [], 0, "", False
    for ch in pats:
        if esc:
            cur += ch
            esc = False
            continue
        if ch == "\\":
            cur += ch
            esc = True
        elif ch == "(":
            depth += 1
            cur += ch
        elif ch == ")":
            depth -= 1
            cur += ch
        elif ch == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _c(label: str, pats: str) -> Concept:
    out = []
    for p in _split_top(pats):
        p = p.strip()
        if not p:
            continue
        # short plain tokens get word boundaries so "gc" doesn't match "magic"
        if len(p) <= 3 and re.fullmatch(r"[a-z0-9]+", p):
            p = rf"\b{p}\b"
        out.append(p)
    return Concept(label, tuple(out))


EXAMPLE = _c("concrete example", r"example|e\.g|for instance|such as|let's say|suppose|imagine|like when")
STAR = (
    _c("situation / context", r"when i|at my|in my (last|previous|current|final)|project|team|internship|college|company|situation"),
    _c("your specific actions", r"\bi (decided|took|built|spoke|talked|proposed|organi[sz]ed|created|led|set up|worked|wrote|suggested|asked|reached|started|scheduled|broke)"),
    _c("result / outcome", r"result|outcome|as a result|eventually|finally|improv|reduc|increas|deliver|succeed|shipped|launched|\d+ ?%"),
    _c("reflection / learning", r"learn|lesson|next time|differently|realis|realiz|taught me"),
)
PROJECT = (
    _c("problem / goal", r"problem|goal|aim|needed|purpose|users|client|requirement"),
    _c("your role / contribution", r"\bi (built|designed|implemented|wrote|led|owned|was responsible|developed|created)|my role|my part"),
    _c("technical decisions & trade-offs", r"chose|choose|decid|trade.?off|instead of|because|alternative|compared"),
    _c("outcome / impact", r"result|impact|reduc|improv|increas|users|\d+ ?%|faster|deployed|launched|grade|award"),
)

T: dict[str, Topic] = {}


def topic(id: str, name: str, category: str, keywords: str = "", actions: tuple[str, ...] = ()) -> Topic:
    t = Topic(id, name, category, tuple(k for k in keywords.split(",") if k), actions)
    T[id] = t
    return t


def q(t: Topic, level: int, text: str, concepts, hint: str, followups: tuple[str, ...] = ()) -> None:
    qid = f"{t.id}_{len(t.questions) + 1}"
    concepts = tuple(_c(*c) if isinstance(c, tuple) else c for c in concepts)
    t.questions.append(BankQuestion(qid, t.id, level, text, concepts, hint, followups))


# --------------------------------------------------------------------------- Java
t = topic("java_oop", "Java OOP & Polymorphism", "technical", "java,oop,polymorphism,inheritance",
          ("Write a small class hierarchy (Shape → Circle/Rectangle) and call methods through the parent type.",
           "Contrast overloading vs overriding in a 10-line example you can explain out loud.",
           "Refactor one if/else chain in your code into polymorphic classes."))
q(t, 1, "What is polymorphism in Java?",
  [("one interface, many forms", r"many forms|multiple forms|one interface|same (method|name|interface)|different behaviou?r"),
   ("compile-time polymorphism (overloading)", r"overload|compile.?time|static (binding|polymorphism)"),
   ("runtime polymorphism (overriding)", r"overrid|run.?time|dynamic (dispatch|binding)|late binding"),
   EXAMPLE],
  "Think about two ways the same method name can behave differently: one decided by the compiler, one while the program runs.",
  ("Can you explain compile-time and runtime polymorphism with a simple Java example?",))
q(t, 2, "What is the difference between an abstract class and an interface in Java, and when would you choose each?",
  [("abstract classes can hold state and constructors", r"state|field|constructor|instance variable"),
   ("a class can implement many interfaces but extend one class", r"multiple (inheritance|interfaces)|implement (many|multiple)|extend (only )?one|single inheritance"),
   ("default/static methods in interfaces (Java 8+)", r"default method|java 8|static method"),
   ("choosing: shared base behaviour vs a capability contract", r"is.?a|can.?do|contract|capabilit|shared (code|behaviou?r)|common code")],
  "Consider what each one can contain (fields? constructors?) and how many of each a class can inherit from.")
q(t, 3, "A payment module has a growing if-else chain over payment types (card, UPI, wallet). How would you refactor it using OOP principles, and how does that help when a new payment type is added?",
  [("common interface / abstract PaymentMethod", r"interface|abstract|strategy"),
   ("polymorphic dispatch replaces the conditionals", r"polymorph|overrid|each (class|type) implements|dynamic dispatch"),
   ("open/closed principle", r"open.?closed|without (modifying|changing)|extend without|ocp"),
   ("factory or registry for creating the right type", r"factory|registry|map of|lookup|dependency injection|spring")],
  "Which design pattern lets each payment type carry its own behaviour behind one common type?")

t = topic("java_collections", "Java Collections", "technical", "java,collections,hashmap,arraylist",
          ("Implement a tiny HashMap (array of buckets + chaining) to see hashing and collisions first-hand.",
           "Memorise the time complexity table for ArrayList, LinkedList, HashMap, TreeMap and HashSet.",
           "Write a multithreaded counter with HashMap, observe the bug, then fix it with ConcurrentHashMap.merge."))
q(t, 1, "What is the difference between ArrayList and LinkedList in Java?",
  [("ArrayList is backed by a dynamic array; LinkedList by linked nodes", r"dynamic array|resizable array|backed by (an )?array|array.?based|node|doubly|linked"),
   ("index access: O(1) vs O(n)", r"o\(1\)|o\(n\)|random access|constant time|index|get\("),
   ("insert/delete in the middle", r"insert|delet|remov|shift"),
   ("memory overhead / cache locality", r"memory|overhead|pointer|cache|referenc")],
  "Picture how the elements are laid out in memory for each one, and what it costs to reach element #500.")
q(t, 2, "How does HashMap work internally in Java?",
  [("hashCode() decides the bucket index", r"hash ?code|hash function|bucket|index"),
   ("collisions handled by chaining (list, then tree)", r"collision|chain|linked list|tree|red.?black"),
   ("equals() compares keys within a bucket", r"equals"),
   ("resizing at the load factor (0.75)", r"load factor|resiz|rehash|0\.75|capacity")],
  "Walk through what happens to a key from the moment you call put(key, value).")
q(t, 2, "Why must you override hashCode() whenever you override equals()?",
  [("contract: equal objects must have equal hash codes", r"contract|equal objects|same hash|must (have|return) (the )?same"),
   ("hash-based collections look up by hash first", r"hashmap|hashset|bucket|look.?up|lookup"),
   ("otherwise duplicates or failed lookups", r"duplicate|not found|can't find|cannot find|fail|null|miss")],
  "Think about what a HashSet does first when you call contains(obj).")
q(t, 3, "Several threads update a shared HashMap of user sessions and you see occasional lost updates. What is going wrong and how would you fix it?",
  [("HashMap is not thread-safe (race condition)", r"not thread.?safe|race|concurren|synchroni[sz]"),
   ("use ConcurrentHashMap", r"concurrenthashmap"),
   ("atomic compound ops: compute/merge/putIfAbsent", r"compute|merge|putifabsent|atomic"),
   ("trade-off vs synchronizedMap / global lock", r"synchronizedmap|lock|contention|segment|throughput")],
  "Is a read-modify-write on a plain HashMap ever safe across threads? What collection was designed for this?")

t = topic("java_core", "Core Java (Strings, Exceptions)", "technical", "java,exceptions,string",
          ("Write a REST error handler that maps three custom exceptions to HTTP status codes.",
           "Explain String pool behaviour with == vs equals() in a short demo."))
q(t, 1, "Why are Strings immutable in Java?",
  [("string pool sharing", r"pool|intern|shar|reuse"),
   ("security (class names, paths, credentials)", r"secur|password|path|class ?load|network"),
   ("thread safety", r"thread"),
   ("hashCode caching for map keys", r"hash|cache|key")],
  "Many references can point at the same String literal. What would go wrong if one of them could change it?")
q(t, 2, "What is the difference between checked and unchecked exceptions in Java?",
  [("checked exceptions must be caught or declared (compile-time)", r"compile|must (be )?(caught|handled|declared)|throws|catch or declare"),
   ("unchecked = RuntimeException and subclasses", r"runtime ?exception|unchecked"),
   ("examples (IOException vs NullPointerException)", r"ioexception|sqlexception|nullpointer|illegalargument|arithmetic|filenotfound"),
   ("when to use each (recoverable vs programming error)", r"recover|programming (error|bug)|caller can|should use")],
  "Which kind does the compiler force you to deal with?")
q(t, 3, "How would you design exception handling for a Spring/REST API so clients get consistent, safe error responses?",
  [("domain-specific custom exceptions", r"custom exception|domain|notfound|business exception"),
   ("global handler (@ControllerAdvice / @ExceptionHandler)", r"controlleradvice|exceptionhandler|global|centrali[sz]"),
   ("map to HTTP status + consistent error body", r"status|404|400|500|error (body|response|format)|problem.?detail"),
   ("log with context, never leak stack traces", r"log|stack ?trace|leak|sensitive|correlation")],
  "Where would you put the code that turns an exception into a response, so each controller doesn't repeat it?")

t = topic("java_concurrency", "Java Concurrency", "technical", "java,thread,concurrency,multithreading",
          ("Build a producer/consumer with a bounded BlockingQueue.",
           "Show why count++ is not atomic, then fix it with AtomicInteger.",
           "Read the ExecutorService and CompletableFuture docs and rewrite one blocking loop."))
q(t, 1, "What is the difference between a process and a thread?",
  [("processes have separate memory; threads share memory", r"own (memory|address)|separate memory|share|shared memory|same memory"),
   ("threads are lighter weight / cheaper to switch", r"light|cheap|context switch|overhead|faster to create"),
   ("communication and isolation trade-off", r"communicat|ipc|isolat|crash|safer")],
  "Focus on memory: what does each one get to itself?")
q(t, 2, "What does the volatile keyword guarantee in Java, and what does it not guarantee?",
  [("visibility of writes across threads", r"visib|main memory|cache|see the latest|other threads"),
   ("prevents reordering / happens-before", r"reorder|happens.?before|memory barrier|fence"),
   ("does not make compound actions atomic (count++)", r"not atomic|atomicity|\+\+|increment|race"),
   ("use Atomic* or synchronized for atomicity", r"atomic(integer|long|reference)?|synchroni[sz]|lock")],
  "If two threads both run counter++ on a volatile int, is the result always correct?")
q(t, 3, "How would you design a system that processes 10,000 image uploads concurrently without exhausting memory or threads?",
  [("fixed-size thread pool (ExecutorService)", r"executor|thread ?pool|fixed"),
   ("bounded queue / backpressure", r"bounded|queue|backpressure|blockingqueue|limit"),
   ("rejection or retry policy", r"reject|retry|caller.?runs|drop|throttl"),
   ("error handling and graceful shutdown", r"future|shutdown|await|exception|timeout|completablefuture")],
  "What stops 10,000 tasks from creating 10,000 threads or filling the heap all at once?")

t = topic("java_jvm", "JVM Memory & Garbage Collection", "technical", "jvm,garbage collection,memory",
          ("Take a heap dump of a toy app with a static-list leak and find it in Eclipse MAT or VisualVM.",
           "Enable GC logging and read one young-gen and one full-GC entry."))
q(t, 1, "What are the stack and the heap in Java memory?",
  [("stack: method frames and local variables, per thread", r"stack.*(local|frame|method|primitive|thread)|(local|frame|method).*stack"),
   ("heap: objects, shared across threads", r"heap.*(object|shared|new)|(object|new).*heap"),
   ("heap is managed by the garbage collector", r"garbage|\bgc\b|collector"),
   ("StackOverflowError vs OutOfMemoryError", r"stackoverflow|outofmemory|recursion")],
  "Where does `new Person()` live, and where does the reference variable pointing to it live?")
q(t, 2, "How does garbage collection work in Java at a high level?",
  [("reachability from GC roots", r"reachab|gc roots|referenc|no longer (used|referenced)"),
   ("generational heap (young / old)", r"young|old|generation|eden|survivor|tenured"),
   ("mark, sweep and compact", r"mark|sweep|compact"),
   ("stop-the-world pauses / collectors (G1, ZGC)", r"stop.?the.?world|pause|g1|zgc|parallel|cms|shenandoah")],
  "How does the JVM decide an object is garbage? And why split the heap into regions by age?")
q(t, 3, "A production Java service's memory keeps growing until it crashes with OutOfMemoryError. How would you investigate?",
  [("capture a heap dump (HeapDumpOnOutOfMemoryError, jmap)", r"heap ?dump|jmap|jcmd|hprof"),
   ("analyse dominators/retained size (MAT, VisualVM)", r"\bmat\b|eclipse|visualvm|dominator|retained|profil"),
   ("common leak sources (static maps, caches, listeners, ThreadLocal)", r"static|cache|listener|threadlocal|leak|unbounded|connection"),
   ("monitor GC logs/metrics and verify the fix", r"gc log|monitor|metric|grafana|prometheus|verify|reproduce")],
  "What artifact would show you which objects are filling the heap and who is holding on to them?")

t = topic("spring_boot", "Spring Boot", "technical", "spring,spring boot,dependency injection",
          ("Build a 3-layer Spring Boot CRUD app with constructor injection and tests.",
           "Turn on SQL logging and find an N+1 query, then fix it with a fetch join."))
q(t, 1, "What is dependency injection, and why does Spring use it?",
  [("dependencies supplied by a container instead of created with `new`", r"inject|container|instead of (creating|new)|provid|ioc|inversion"),
   ("loose coupling", r"loose|decoupl|coupling"),
   ("easier testing with mocks", r"test|mock"),
   ("constructor injection / beans", r"constructor|bean|@autowired|autowir")],
  "Who creates the objects your class needs: the class itself, or something else?")
q(t, 2, "Explain the difference between @Component, @Service, @Repository and @Controller in Spring.",
  [("all are stereotypes picked up by component scanning", r"component scan|stereotype|bean|specialization|all are"),
   ("semantic layering (business/service, data access, web)", r"layer|business|service layer|data access|dao|web"),
   ("@Repository adds persistence exception translation", r"exception translation|dataaccessexception|translat"),
   ("@Controller handles web requests (@RestController)", r"request|restcontroller|http|endpoint|mvc")],
  "Are they technically different, or mostly about meaning? Is there one with extra behaviour?")
q(t, 3, "Your Spring Boot API's response time spikes under load and you suspect the database. How would you diagnose and fix it?",
  [("measure first: Actuator metrics, APM, profiling", r"actuator|metric|apm|profil|trace|monitor|micrometer|new relic|datadog"),
   ("N+1 queries / lazy loading via SQL logs", r"n ?\+ ?1|lazy|eager|fetch join|show.?sql|sql log"),
   ("indexes and query plans", r"index|explain|query plan|slow query"),
   ("connection pool, caching, pagination", r"pool|hikari|cach|paginat|batch")],
  "Before changing code, how would you prove where the time is going?")

# --------------------------------------------------------------------------- Python
t = topic("python_core", "Python Core", "technical", "python,list,tuple,dictionary",
          ("Predict, then run, small snippets about mutability, copying and default arguments.",
           "Read the Python data model docs section on mutable vs immutable types."))
q(t, 1, "What is the difference between a list and a tuple in Python?",
  [("lists are mutable, tuples are immutable", r"mutable|immutable|can't (be )?chang|cannot (be )?chang|modif"),
   ("tuples are hashable and can be dict keys", r"hash|dict(ionary)? key|key"),
   ("performance / memory", r"faster|memory|performance|lighter"),
   ("typical use cases", r"fixed|record|coordinates|return multiple|heterogen|homogen|collection")],
  "Try changing the first element of each one. What happens?")
q(t, 2, "What is the difference between a shallow copy and a deep copy in Python?",
  [("shallow copy duplicates only the outer container", r"outer|top.?level|new (list|object|container)|one level"),
   ("nested objects are shared by reference", r"nested|inner|reference|shar|point to the same"),
   ("deep copy recursively copies everything", r"recursiv|everything|all (nested|levels)|independent|fully"),
   ("copy.copy / copy.deepcopy", r"copy\.copy|deepcopy|copy module|\[:\]|list\(")],
  "Copy a list of lists, then append to one of the inner lists. Which copy notices?")
q(t, 2, "Why is a mutable default argument like `def add(item, bucket=[])` a common Python bug?",
  [("default is evaluated once, at function definition", r"once|definition|defined|created once"),
   ("same list shared across calls", r"shared|same (list|object)|persist|accumulat|previous calls"),
   ("use None as a sentinel", r"none")],
  "When exactly is `[]` created: each call, or once?")
q(t, 3, "How does Python manage memory?",
  [("reference counting", r"reference count|refcount|ref count"),
   ("cyclic garbage collector", r"cycl|garbage collect|\bgc\b|generation"),
   ("private heap / pymalloc allocator", r"private heap|pymalloc|allocator|arena|heap"),
   ("tools: del, weakref, gc module, tracemalloc", r"\bdel\b|weakref|tracemalloc|gc module|gc\.collect")],
  "What happens to an object's bookkeeping each time a new name points to it? And what about objects that point to each other?")

t = topic("python_advanced", "Advanced Python", "technical", "python,decorator,generator,asyncio,gil",
          ("Write a @timed decorator with functools.wraps and a parameterised @retry(n) decorator.",
           "Process a 2 GB log file with a generator pipeline and compare memory with a list.",
           "Benchmark threads vs processes vs asyncio on a CPU-bound and an I/O-bound task."))
q(t, 1, "What is a decorator in Python?",
  [("a function that takes a function and returns a wrapped one", r"function that (takes|wraps|returns)|wrap|higher.?order|takes a function"),
   ("@ syntax", r"@"),
   ("adds behaviour without changing the original code", r"without (modifying|changing)|add (behaviou?r|functionality)|extend"),
   ("use cases: logging, timing, auth, caching", r"log|tim|auth|cach|retry|lru_cache|login_required|route")],
  "What does `@timer` above a function actually rewrite that function into?")
q(t, 2, "What is the difference between a generator and a list, and when would you use a generator?",
  [("yield produces values lazily", r"yield|lazy|lazily|on demand|one at a time"),
   ("memory efficiency", r"memory"),
   ("single pass / iterator protocol", r"once|single pass|iterator|next\(|exhaust"),
   ("use cases: large files, streams, pipelines", r"large|file|stream|infinite|pipeline|big data")],
  "What happens to memory if you read a 10 GB file into a list versus iterating over it?")
q(t, 3, "What is the GIL, and how does it affect CPU-bound versus I/O-bound Python programs? How would you speed up each?",
  [("one thread executes Python bytecode at a time", r"one thread|single thread|global interpreter lock|only one|mutex"),
   ("CPU-bound: use multiprocessing / native extensions", r"multiprocess|process pool|processpoolexecutor|numpy|c extension|cython|numba"),
   ("I/O-bound: threads or asyncio work well (GIL released on I/O)", r"asyncio|async|await|threadpool|i/o|io.?bound.*thread|released"),
   ("free-threaded builds (3.13+) / trade-offs", r"free.?threaded|no.?gil|3\.13|pep 703|nogil")],
  "During a network call, does a Python thread keep holding the lock?")

t = topic("testing", "Testing & Quality", "technical", "testing,pytest,junit,unit test,jest",
          ("Write tests for one function at three levels: unit, integration, end-to-end.",
           "Pick a flaky test and categorise its cause (timing, shared state, external dependency)."))
q(t, 1, "What is the difference between unit tests and integration tests?",
  [("unit tests check one unit in isolation", r"isolat|single (function|unit|class)|one (function|unit|component)|small"),
   ("integration tests check components together with real dependencies", r"together|combin|multiple (components|modules)|database|real|interact"),
   ("speed / feedback trade-off", r"fast|slow|speed|quick"),
   ("you need both (testing pyramid)", r"pyramid|both|balance|more unit")],
  "Which one would touch a real database?")
q(t, 2, "What is mocking, and when can over-mocking hurt you?",
  [("replace a dependency with a controllable fake", r"fake|replace|stub|simulat|substitut|double"),
   ("isolate the unit / control external behaviour", r"isolat|control|external|api|network|database"),
   ("over-mocking couples tests to implementation", r"implementation detail|brittle|fragile|refactor|coupl"),
   ("false confidence: tests pass, production breaks", r"false|pass but|doesn't (catch|reflect)|real behaviou?r|confidence")],
  "If you mock every collaborator, what are you actually testing?")
q(t, 3, "A test fails roughly 1 in 20 CI runs. How would you track down the cause?",
  [("reproduce: rerun in a loop, fix random seeds", r"reproduc|loop|repeat|rerun|seed|run it (many|multiple)"),
   ("timing / race conditions / async waits", r"timing|race|async|sleep|wait|timeout"),
   ("shared state or test-order dependence", r"shared state|order|global|leak|cleanup|isolation"),
   ("external dependencies: time, network, randomness", r"network|external|clock|time zone|date|random|third.?party")],
  "What would make the same test behave differently between runs with identical code?")

# --------------------------------------------------------------------------- Data / SQL
t = topic("sql", "SQL Querying", "technical", "sql,mysql,postgresql,queries,joins",
          ("Solve 15 join/aggregation problems on a sample schema (e.g. employees, orders).",
           "Rewrite three GROUP BY queries using window functions and compare results.",
           "Practise explaining NULL handling in joins and aggregates."))
q(t, 1, "What is the difference between INNER JOIN and LEFT JOIN?",
  [("INNER JOIN returns only matching rows", r"only (the )?match|both tables|common|intersection"),
   ("LEFT JOIN keeps all rows from the left table", r"all (the )?(rows|records).*left|left table|every row"),
   ("non-matching right columns become NULL", r"null"),
   EXAMPLE],
  "If a customer has never placed an order, which join still shows that customer?")
q(t, 2, "What is the difference between WHERE and HAVING in SQL?",
  [("WHERE filters rows before grouping", r"before|rows|individual"),
   ("HAVING filters groups after aggregation", r"after|group|aggregat"),
   ("aggregate conditions (COUNT/SUM) belong in HAVING", r"count|sum|avg|max|aggregate function"),
   EXAMPLE],
  "Can you write `WHERE COUNT(*) > 5`? Why not?")
q(t, 2, "How would you find the second-highest salary from an employees table?",
  [("subquery: MAX below the overall MAX", r"max.*<|less than.*max|max.*max|subquery"),
   ("ORDER BY ... DESC with LIMIT/OFFSET", r"order by|desc|limit|offset|top"),
   ("handle duplicates / ties with DISTINCT or DENSE_RANK", r"distinct|dense_rank|tie|duplicate|rank"),
   ("handle the case where it doesn't exist", r"null|no second|doesn't exist|only one|empty")],
  "What if two people share the highest salary?")
q(t, 3, "Explain window functions, and describe a query that computes each customer's running total of purchases by date.",
  [("OVER() clause computes across related rows", r"over ?\(|window"),
   ("PARTITION BY customer", r"partition by"),
   ("ORDER BY date inside the window", r"order by"),
   ("unlike GROUP BY, rows are not collapsed", r"not collaps|keeps? (all|each|every) row|without grouping|each row|unlike group by")],
  "How can you aggregate without losing the individual rows?")

t = topic("databases", "Databases & Indexing", "technical", "database,postgresql,mysql,mongodb,index,transactions",
          ("Run EXPLAIN on a slow query, add an index, and compare plans.",
           "Write down an example of each ACID property failing and how a database prevents it."))
q(t, 1, "What is a primary key and a foreign key?",
  [("primary key uniquely identifies each row (unique, not null)", r"unique|identif|not null"),
   ("foreign key references another table's key", r"referenc|another table|other table|link|relationship"),
   ("referential integrity", r"integrity|consisten|orphan|cascade")],
  "How does the orders table know which customer each order belongs to?")
q(t, 2, "What is a database index, and what are its trade-offs?",
  [("data structure (usually a B-tree) for fast lookups", r"b.?tree|data structure|lookup|sorted|pointer|hash index"),
   ("avoids full table scans", r"full (table )?scan|scan|faster (read|search|quer)|speed"),
   ("slower writes and extra storage", r"write|insert|update|storage|space|slower"),
   ("selectivity / composite index column order", r"selectiv|cardinality|composite|column order|leftmost|covering")],
  "Why not index every column?")
q(t, 2, "Explain the ACID properties of a database transaction.",
  [("Atomicity: all or nothing", r"atomic|all or nothing|rollback"),
   ("Consistency: valid state, constraints hold", r"consisten|constraint|valid state"),
   ("Isolation: concurrent transactions don't interfere", r"isolat|concurren|interfere|dirty read"),
   ("Durability: committed data survives crashes", r"durab|crash|persist|permanent|survive")],
  "Think of a bank transfer between two accounts. What could go wrong at each step?")
q(t, 3, "When would you denormalize a database, and what risks does that introduce?",
  [("read-heavy workloads / avoid expensive joins", r"read|join|performance|faster quer"),
   ("reporting, analytics or caching use cases", r"report|analytic|dashboard|cache|warehouse"),
   ("data duplication and update anomalies", r"duplicat|redundan|anomal|inconsisten|out of sync"),
   ("keeping copies in sync (triggers, jobs, events)", r"trigger|job|event|sync|materiali[sz]ed view")],
  "What do you gain by storing the same fact twice, and what do you now have to maintain?")

t = topic("data_analysis", "Data Analysis with pandas", "technical", "pandas,excel,data cleaning,analysis,numpy",
          ("Clean a messy public dataset end-to-end and document every decision.",
           "Practise merge/groupby/pivot_table on two related CSVs.",
           "Write a sanity-check checklist (row counts, duplicates, totals) to run before any report."))
q(t, 1, "How do you handle missing values in a dataset?",
  [("detect and quantify (isnull, counts per column)", r"isnull|isna|count|identify|check|how many|percentage"),
   ("drop rows or columns when appropriate", r"drop"),
   ("impute: mean / median / mode / forward-fill / model", r"impute|mean|median|mode|fill|interpolat"),
   ("understand why data is missing / add a flag", r"why|reason|random|pattern|flag|indicator|bias")],
  "Before choosing to drop or fill, what should you find out about the missing values?")
q(t, 2, "What is the difference between merge, join and concat in pandas?",
  [("merge combines on columns, SQL-style", r"merge.*(column|key|sql)|sql"),
   ("join combines on the index", r"join.*index|index"),
   ("concat stacks along an axis", r"concat.*(stack|append|axis)|stack|axis|append"),
   ("how= inner / left / outer", r"inner|left|outer|how=")],
  "Which one would you use to stack January's and February's sales tables on top of each other?")
q(t, 2, "Explain groupby in pandas using the split-apply-combine idea.",
  [("split rows into groups by key", r"split|group(s)? by|categor"),
   ("apply an aggregation or transformation", r"apply|aggregat|sum|mean|count|agg"),
   ("combine the results", r"combin|result"),
   ("agg vs transform", r"transform|agg\(|multiple aggregat|named aggregat")],
  "Describe the three stages of computing average sales per region.")
q(t, 3, "A monthly sales dashboard suddenly shows revenue doubled. How would you investigate before reporting it?",
  [("check the pipeline for duplicates or join fan-out", r"duplicat|join|fan.?out|double count|pipeline|etl"),
   ("reconcile with the source system / raw totals", r"source|raw|reconcil|finance|compare|cross.?check"),
   ("break down by segment to localise the change", r"segment|region|product|breakdown|drill|by day|which"),
   ("definitions, currency, time zone, date range", r"definition|currency|time ?zone|date range|filter|metric"),
   ("communicate with stakeholders before publishing", r"stakeholder|communicat|flag|inform|team|manager")],
  "Is the business really booming, or did something change in the data? How would you tell?")

t = topic("statistics", "Statistics & Experimentation", "technical", "statistics,a/b testing,hypothesis,probability",
          ("Explain p-values, confidence intervals and power to a non-technical friend.",
           "Run a simulated A/B test in Python and see how peeking inflates false positives."))
q(t, 1, "What is the difference between mean, median and mode, and when is the median a better summary than the mean?",
  [("definitions of each", r"average|middle|most (frequent|common)"),
   ("median is robust to outliers / skew", r"outlier|skew|extreme"),
   ("example such as income or house prices", r"income|salar|house|price|wealth|example")],
  "What happens to the average salary of a room when a billionaire walks in?")
q(t, 2, "Explain a p-value in simple terms.",
  [("probability of data this extreme assuming the null is true", r"assum.*null|null hypothesis|if the null|by chance|extreme"),
   ("not the probability the null hypothesis is true", r"not the probability|doesn't (mean|tell)|does not (mean|tell)|misinterpret"),
   ("significance threshold (e.g. 0.05)", r"0\.05|5 ?%|threshold|significan|alpha"),
   ("practical significance / effect size", r"effect size|practical|magnitude|confidence interval")],
  "It's a statement about the data given an assumption, not about the assumption itself.")
q(t, 2, "What is the difference between correlation and causation?",
  [("correlation is association between variables", r"associat|move together|relationship|related"),
   ("confounding variables", r"confound|third variable|hidden|lurking|common cause"),
   ("randomised experiments establish causation", r"experiment|random|a/?b|controlled|rct"),
   EXAMPLE],
  "Ice-cream sales and drownings rise together. Why?")
q(t, 3, "How would you design an A/B test for a new checkout button, and decide whether it worked?",
  [("hypothesis and primary metric (conversion)", r"hypothes|metric|conversion"),
   ("random assignment with a control group", r"random|control|split"),
   ("sample size / power calculated in advance", r"sample size|power|minimum detectable|mde"),
   ("significance and avoiding peeking", r"significan|p.?value|confidence|peek|stop early|duration"),
   ("guardrail metrics / novelty effects", r"guardrail|novelty|revenue|side effect|secondary")],
  "What do you need to decide before the test starts, not after?")

t = topic("data_viz", "Data Visualisation & Dashboards", "technical", "tableau,power bi,visualization,dashboard,matplotlib",
          ("Redesign one misleading chart you find online and explain the fixes.",
           "Build a one-page KPI dashboard in Power BI/Tableau with drill-downs."))
q(t, 1, "How do you choose the right chart for your data?",
  [("comparisons: bar charts", r"bar"),
   ("trends over time: line charts", r"line|trend|time"),
   ("distributions: histogram / box plot", r"histogram|box|distribution"),
   ("relationships: scatter plots", r"scatter|relationship|correlat")],
  "Start from the question the chart must answer: compare, trend, distribution or relationship?")
q(t, 2, "What makes a chart or dashboard misleading, and how do you avoid it?",
  [("truncated or inconsistent axes", r"axis|axes|truncat|zero|baseline|scale"),
   ("cherry-picked time ranges", r"cherry|range|period|selective"),
   ("3D effects, dual axes, poor colour use", r"3d|dual|colou?r|pie"),
   ("context: labels, units, sources", r"label|context|unit|source|annotat")],
  "Look at where the y-axis starts.")
q(t, 3, "Executives want a single KPI dashboard for a subscription business. What would you put on it and why?",
  [("recurring revenue (MRR/ARR)", r"mrr|arr|recurring|revenue"),
   ("churn / retention", r"churn|retention|cohort"),
   ("acquisition efficiency (CAC, LTV)", r"cac|ltv|acquisition|lifetime|signup"),
   ("trends against targets", r"target|goal|trend|month over month|mom|yoy"),
   ("drill-down by segment", r"segment|drill|filter|region|plan")],
  "What few numbers tell an executive whether the business is healthy and why?")

# --------------------------------------------------------------------------- Web
t = topic("html_css", "HTML, CSS & Accessibility", "technical", "html,css,accessibility,tailwind,responsive",
          ("Rebuild one page using only semantic elements and check it with a screen reader.",
           "Build the same layout with Flexbox and with Grid.",
           "Run axe DevTools on a project and fix every issue it reports."))
q(t, 1, "What is semantic HTML and why does it matter?",
  [("meaningful elements (header, nav, main, article, button)", r"header|nav|main|article|section|footer|button|meaning"),
   ("accessibility for screen readers", r"accessib|screen reader|a11y|assistive"),
   ("SEO", r"seo|search engine"),
   ("maintainability / readability", r"maintain|readab|structure")],
  "Compare `<div onclick>` with `<button>`. What does the browser give you for free?")
q(t, 2, "Explain the CSS box model and what box-sizing: border-box changes.",
  [("content, padding, border, margin", r"content.*padding|padding.*border|margin"),
   ("default content-box: width excludes padding and border", r"content.?box|exclud|added|adds"),
   ("border-box: width includes padding and border", r"border.?box.*(includ|total)|includ")],
  "If width is 200px and padding is 20px, how wide is the box under each setting?")
q(t, 2, "When would you use Flexbox versus CSS Grid?",
  [("Flexbox is one-dimensional (row or column)", r"one.?dimension|single (row|axis|direction)|1d|row or column"),
   ("Grid is two-dimensional (rows and columns)", r"two.?dimension|rows and columns|2d"),
   ("alignment and distribution of items", r"align|justify|distribut|space"),
   ("example layouts (navbar vs page layout)", r"nav|page layout|card|gallery|dashboard|example")],
  "Think about a navbar versus a whole page layout.")
q(t, 3, "How would you make a complex web page accessible to keyboard and screen-reader users?",
  [("semantic elements and landmarks", r"semantic|landmark|heading|nav|main"),
   ("keyboard support: focus order, visible focus, no traps", r"keyboard|tab|focus"),
   ("ARIA only where native semantics fall short", r"aria"),
   ("alt text, labels and colour contrast", r"alt|label|contrast|colou?r"),
   ("test with screen readers and automated tools", r"screen reader|nvda|voiceover|axe|lighthouse|test")],
  "Try using the page with only the Tab key. What breaks?")

t = topic("javascript", "JavaScript", "technical", "javascript,js,typescript,node,async",
          ("Predict the output of 10 event-loop puzzles (setTimeout vs Promise.then).",
           "Implement a counter and a memoize helper using closures."))
q(t, 1, "What is the difference between var, let and const in JavaScript?",
  [("var is function-scoped; let/const are block-scoped", r"function.?scope|block.?scope|scope"),
   ("hoisting and the temporal dead zone", r"hoist|temporal dead|tdz|before declaration"),
   ("const prevents reassignment, not mutation", r"reassign|mutat|object.*change|change.*propert"),
   ("prefer const, then let", r"prefer|default|avoid var|use const")],
  "What does a var declared inside an if-block look like from outside the block?")
q(t, 2, "Explain closures in JavaScript with an example.",
  [("a function keeps access to its lexical scope", r"lexical|scope|remember|access"),
   ("works even after the outer function has returned", r"after.*return|returned|outer function"),
   ("practical example: counter, private state, memoisation", r"counter|private|memo|example|factory|once"),
   ("the classic var-in-loop pitfall", r"loop|var|settimeout")],
  "How can an inner function still see a variable after its outer function finished?")
q(t, 2, "How does the JavaScript event loop work?",
  [("single-threaded call stack", r"single.?thread|call stack|stack"),
   ("async work handled by Web APIs / libuv", r"web api|browser api|libuv|background|async"),
   ("task (macrotask) queue, e.g. setTimeout", r"task queue|callback queue|macrotask|settimeout"),
   ("microtasks (promises) run before the next task", r"microtask|promise|then")],
  "Which logs first: setTimeout(…, 0) or Promise.resolve().then(…)?")
q(t, 3, "What's the difference between Promise.all, Promise.allSettled and Promise.race, and when can each be risky?",
  [("all: resolves with every result, rejects fast on the first failure", r"all.*(reject|fail)|first (failure|rejection)|fail fast"),
   ("allSettled: waits for everything, reports each outcome", r"allsettled|every (outcome|result)|status|both (fulfilled|rejected)"),
   ("race: settles with the first to settle (e.g. timeouts)", r"race|first (one|to)|timeout"),
   ("risks: unbounded concurrency, lost errors, no cancellation", r"concurren|limit|cancel|abort|unhandled|lost|rate")],
  "If you fire 1,000 API calls with Promise.all and one fails, what happens to the other 999?")

t = topic("react", "React", "technical", "react,next.js,redux,hooks,frontend",
          ("Build a search-as-you-type list with debouncing and virtualisation.",
           "Find one useEffect in your code with a wrong dependency array and fix it.",
           "Profile a slow component with React DevTools Profiler."))
q(t, 1, "What is the difference between state and props in React?",
  [("props come from the parent and are read-only", r"parent|read.?only|passed|immutable"),
   ("state is owned and updated by the component", r"own|internal|local|managed|setstate|usestate"),
   ("state changes trigger re-renders", r"re.?render|render"),
   ("lifting state up to share it", r"lift|share|common parent|context")],
  "Who is allowed to change each one?")
q(t, 2, "What does the dependency array of useEffect do, and what bugs come from getting it wrong?",
  [("effect re-runs when a dependency changes", r"re.?run|chang|whenever"),
   ("empty array: runs once after mount", r"empty|once|mount"),
   ("missing deps: stale closures / stale values", r"stale|old value|missing"),
   ("objects/functions recreated every render: infinite loops", r"infinite|loop|every render|usecallback|usememo"),
   ("cleanup functions", r"cleanup|clean up|unsubscribe|return a function")],
  "What happens if the effect reads a prop that isn't listed?")
q(t, 3, "A React list of 5,000 items re-renders slowly as the user types in a search box. How would you improve it?",
  [("profile first with React DevTools", r"profil|devtools|measure"),
   ("memoisation: React.memo, useMemo, useCallback", r"memo|usememo|usecallback"),
   ("virtualise the list (react-window)", r"virtuali|window|react.?window|only render visible"),
   ("debounce or useDeferredValue / startTransition", r"debounc|throttl|deferred|transition"),
   ("stable keys", r"key")],
  "Does the browser really need 5,000 DOM rows when only 20 are visible?")

t = topic("http_rest", "HTTP & REST APIs", "technical", "rest,api,http,fastapi,express,flask,django",
          ("Design the endpoints, status codes and pagination for a small API before writing any code.",
           "Implement JWT auth with refresh tokens and document the threat model."))
q(t, 1, "What are the common HTTP methods, and how do they map to CRUD operations?",
  [("GET reads", r"get.*(read|retriev|fetch)"),
   ("POST creates", r"post.*(creat|new|add)"),
   ("PUT / PATCH update", r"put|patch"),
   ("DELETE removes", r"delete"),
   ("idempotency / safety", r"idempot|safe")],
  "Match each verb to Create, Read, Update and Delete.")
q(t, 2, "What is the difference between authentication and authorization, and where do JWTs fit in?",
  [("authentication = who you are", r"who you are|identity|verify (the )?user|login"),
   ("authorization = what you may do", r"what you (can|are allowed)|permission|access|role"),
   ("JWT: signed token carrying claims", r"sign|claim|token|payload"),
   ("expiry, storage and revocation trade-offs", r"expir|revoc|refresh|stateless|httponly|storage|blacklist")],
  "Logging in and being allowed to delete a post are two different checks.")
q(t, 2, "What is CORS, and why do browsers enforce it?",
  [("same-origin policy", r"same.?origin|origin"),
   ("server opts in with Access-Control-Allow-* headers", r"access.?control|header|allow"),
   ("preflight OPTIONS requests", r"preflight|options"),
   ("protects users' browsers, not the server", r"protect|user|cookie|malicious|browser")],
  "Why does curl succeed while the same request fails in the browser?")
q(t, 3, "How would you design a REST API for a paginated, filterable product catalogue that stays fast as it grows?",
  [("resource naming and query parameters for filters", r"/products|query param|filter|resource"),
   ("cursor-based vs offset pagination", r"cursor|offset|keyset|page"),
   ("indexes and caching (ETag, CDN, Redis)", r"index|cach|etag|cdn|redis"),
   ("versioning, validation and rate limiting", r"version|validat|rate limit|throttl")],
  "What happens to `OFFSET 1000000` on a big table?")

# --------------------------------------------------------------------------- CS fundamentals
t = topic("dsa", "Data Structures & Algorithms", "technical", "algorithms,data structures,dsa,leetcode,complexity",
          ("Do 2 problems per day on arrays/hashing and say the complexity aloud before coding.",
           "Implement stack, queue and linked list from scratch.",
           "Practise the slow/fast pointer and sliding-window patterns."))
q(t, 1, "What is Big-O notation, and what is the time complexity of searching in an array versus a hash table?",
  [("describes how cost grows with input size (upper bound)", r"grow|input size|upper bound|worst|scal"),
   ("linear search in an array: O(n)", r"o\(n\)|linear"),
   ("hash table lookup: O(1) on average", r"o\(1\)|constant"),
   ("binary search on sorted data: O(log n)", r"log|binary search|sorted")],
  "How many elements might you inspect in the worst case for each structure?")
q(t, 2, "When would you use a stack versus a queue? Give real examples.",
  [("stack is LIFO", r"lifo|last.?in"),
   ("queue is FIFO", r"fifo|first.?in"),
   ("stack examples: undo, call stack, bracket matching, DFS", r"undo|call stack|bracket|parenthes|dfs|back button"),
   ("queue examples: scheduling, BFS, print jobs", r"schedul|bfs|print|request|order|buffer|line")],
  "Think of the browser's back button versus a line at a ticket counter.")
q(t, 3, "How would you detect a cycle in a linked list, and what is the space complexity of your approach?",
  [("slow and fast pointers (Floyd's algorithm)", r"slow|fast|floyd|tortoise|hare|two pointers"),
   ("if they meet, there is a cycle", r"meet|same node|equal|catch up"),
   ("O(1) extra space", r"o\(1\)|constant space"),
   ("alternative: hash set of visited nodes, O(n) space", r"hash ?set|visited|o\(n\) space|set")],
  "Imagine two runners on a circular track at different speeds.")

t = topic("system_design", "System Design", "technical", "system design,microservices,scalability,distributed,aws,docker,kubernetes",
          ("Work through three classic designs (URL shortener, chat, news feed) using a fixed template: requirements → API → data → scale.",
           "Learn the numbers: latency of memory vs disk vs network, typical QPS per server."))
q(t, 1, "What is the difference between horizontal and vertical scaling?",
  [("vertical: a bigger machine", r"vertical.*(bigger|more (cpu|ram|power)|upgrade)|bigger machine|scale up"),
   ("horizontal: more machines", r"horizontal.*(more|add) (machines|servers|nodes)|more machines|more servers|scale out"),
   ("limits and cost trade-offs", r"limit|cost|ceiling|single point|expensive"),
   ("needs stateless services and a load balancer", r"stateless|load balanc|session")],
  "What happens when you can't buy a bigger server?")
q(t, 2, "What is caching, and what problems can a cache introduce?",
  [("store frequently used data in fast storage", r"fast|memory|frequent|redis|memcache"),
   ("invalidation and stale data", r"invalidat|stale|outdated|consisten"),
   ("eviction policies (LRU, TTL)", r"lru|ttl|evict|expir"),
   ("stampede / thundering herd", r"stampede|thundering|herd|cold")],
  "There are only two hard things in computer science…")
q(t, 3, "How would you design a URL shortener like bit.ly?",
  [("short key generation (base62, counter or hash) and collisions", r"base ?62|hash|counter|collision|unique id|key"),
   ("storage: key-value or relational DB", r"database|key.?value|dynamo|cassandra|postgres|mysql|redis|store"),
   ("redirect path is read-heavy: cache it", r"cach|read.?heavy|redirect|301|302"),
   ("scale, analytics, expiry and abuse prevention", r"scal|analytic|expir|abuse|spam|rate|shard|replica")],
  "Start with the two operations: create a short link, and follow one.")

# --------------------------------------------------------------------------- ML
t = topic("ml_fundamentals", "ML Fundamentals", "technical", "machine learning,scikit-learn,sklearn,regression,classification",
          ("Train a model on a small dataset and plot train vs validation error as complexity grows.",
           "Write a leakage checklist and apply it to a past project."))
q(t, 1, "What is the difference between supervised and unsupervised learning?",
  [("supervised learns from labelled data", r"label"),
   ("unsupervised finds structure without labels", r"without label|no label|unlabel|structure|pattern|group"),
   ("examples: classification/regression vs clustering", r"classif|regress|cluster|k.?means|pca")],
  "Do you have the 'right answers' in your training data or not?")
q(t, 2, "Explain the bias-variance trade-off.",
  [("high bias: too simple, underfits", r"bias.*(simple|underfit)|underfit"),
   ("high variance: too sensitive, overfits", r"variance.*(overfit|sensitiv|noise)|overfit"),
   ("total error balances the two", r"trade.?off|balance|total error|sweet spot"),
   ("controls: model complexity, regularisation, more data", r"complex|regulari|more data|ensembl|cross.?valid")],
  "Compare a straight line and a degree-20 polynomial fitted to 10 points.")
q(t, 2, "How do you detect and prevent overfitting?",
  [("gap between training and validation performance", r"train.*(valid|test)|gap|validation"),
   ("cross-validation", r"cross.?valid|k.?fold"),
   ("regularisation (L1/L2, dropout)", r"regulari|l1|l2|dropout|lasso|ridge"),
   ("more data, simpler model, early stopping", r"more data|simpler|early stop|augment|prun|fewer features")],
  "What would the learning curves look like?")
q(t, 3, "Your model scores 99% accuracy offline but performs poorly in production. What could be happening?",
  [("data leakage", r"leak"),
   ("train/serve skew or distribution shift", r"skew|shift|drift|different distribution|production data"),
   ("class imbalance makes accuracy misleading", r"imbalanc|accuracy (is )?mislead|precision|recall"),
   ("monitoring and retraining", r"monitor|retrain|feedback")],
  "Is 99% suspicious? Which features might have peeked at the answer?")

t = topic("ml_evaluation", "Model Evaluation", "technical", "metrics,evaluation,precision,recall,auc",
          ("Compute precision, recall, F1 and PR-AUC by hand for a tiny confusion matrix.",
           "Pick a decision threshold from a cost matrix instead of using 0.5."))
q(t, 1, "What is a confusion matrix?",
  [("TP, FP, TN, FN", r"true positive|false positive|true negative|false negative|tp|fp"),
   ("predicted vs actual classes", r"predict|actual"),
   ("metrics derived from it (precision, recall)", r"precision|recall|accuracy|f1")],
  "Draw a 2×2 grid: predicted on one axis, actual on the other.")
q(t, 2, "When would you prefer precision over recall, and vice versa?",
  [("precision when false positives are costly (spam filter)", r"false positive|spam"),
   ("recall when false negatives are costly (disease, fraud)", r"false negative|disease|cancer|fraud|miss"),
   ("threshold trade-off / F1", r"threshold|f1|trade.?off|balance")],
  "Would you rather miss a cancer diagnosis or send a healthy person for another test?")
q(t, 3, "How would you evaluate a fraud model where only 0.5% of transactions are fraudulent?",
  [("accuracy is misleading with imbalance", r"accuracy|imbalanc|99\.5"),
   ("PR-AUC, recall, precision@k", r"pr.?auc|precision|recall|average precision|@k"),
   ("threshold chosen by business cost", r"cost|threshold|business|loss"),
   ("class weights / resampling", r"weight|smote|resampl|oversampl|undersampl"),
   ("time-based validation split", r"time|temporal|out.?of.?time|future")],
  "A model that predicts 'not fraud' every time is 99.5% accurate. Is it useful?")

t = topic("deep_learning", "Deep Learning", "technical", "deep learning,pytorch,tensorflow,neural network,nlp,llm,transformer",
          ("Implement a 2-layer network with backprop in NumPy.",
           "Read 'Attention Is All You Need' and explain self-attention with a 3-token example."))
q(t, 1, "What is an activation function, and why do neural networks need one?",
  [("introduces non-linearity", r"non.?linear"),
   ("without it, stacked layers collapse to a linear model", r"linear (model|function)|collapse|just a linear|matrix multiplication"),
   ("examples: ReLU, sigmoid, tanh, GELU", r"relu|sigmoid|tanh|softmax|gelu"),
   ("vanishing gradients", r"vanish|gradient|saturat")],
  "What do you get if you multiply several matrices together with nothing in between?")
q(t, 2, "Explain how backpropagation and gradient descent work together.",
  [("forward pass computes the loss", r"forward|loss|prediction"),
   ("chain rule computes gradients layer by layer", r"chain rule|gradient|derivative|backward"),
   ("weights updated against the gradient by the learning rate", r"learning rate|update|step|subtract|minimi"),
   ("mini-batches / optimisers (SGD, Adam)", r"batch|sgd|adam|optimi[sz]er|momentum")],
  "Backprop finds the direction; gradient descent takes the step.")
q(t, 3, "How do transformers process sequences differently from RNNs?",
  [("self-attention over all positions at once", r"attention|all (tokens|positions|words)"),
   ("parallel training instead of step-by-step recurrence", r"parallel|sequential|recurren|step by step"),
   ("positional encodings provide order", r"position"),
   ("long-range dependencies vs quadratic cost", r"long.?range|long dependencies|vanish|quadratic|n\^?2|context length")],
  "An RNN reads token by token. How does a transformer see the whole sentence?")

t = topic("ml_ops", "ML Deployment & MLOps", "technical", "mlops,deployment,docker,mlflow,model serving",
          ("Wrap a trained model in a FastAPI service with input validation and a Dockerfile.",
           "Set up a drift check that compares live feature distributions with training data."))
q(t, 1, "Why is reproducibility important in ML projects, and how do you achieve it?",
  [("fix random seeds", r"seed"),
   ("version data, code and models", r"version|git|dvc"),
   ("pin environments / containers", r"environment|requirements|docker|container|pin"),
   ("experiment tracking (MLflow, W&B)", r"mlflow|weights|w&b|track|log")],
  "If a colleague re-runs your notebook next month, what could change the result?")
q(t, 2, "How would you deploy a trained ML model as an API?",
  [("serialise the model artifact", r"pickle|joblib|onnx|save|serial|artifact"),
   ("serve via FastAPI/Flask in a container", r"fastapi|flask|docker|container|endpoint|torchserve|sagemaker"),
   ("same preprocessing as training, validate inputs", r"preprocess|pipeline|validat|schema|same transform"),
   ("monitoring, versioning, latency", r"monitor|version|latency|log|scal")],
  "What has to happen to a raw request before the model can predict on it?")
q(t, 3, "How do you monitor a model in production and decide when to retrain?",
  [("data / feature drift", r"drift|distribution|shift|psi|ks test"),
   ("performance once labels arrive (delayed feedback)", r"label|ground truth|delay|performance|accuracy|metric"),
   ("alerts and thresholds", r"alert|threshold|dashboard"),
   ("retraining pipeline, shadow or A/B rollout", r"retrain|pipeline|shadow|canary|a/?b|rollback|schedule")],
  "You often don't get labels immediately. What can you watch in the meantime?")

# --------------------------------------------------------------------------- HR / behavioural
HR_ACTIONS = ("Prepare 6 STAR stories (Situation, Task, Action, Result) and rehearse each in under 2 minutes.",
              "Quantify results where you can (time saved, % improvement, users affected).",
              "End each story with what you learned or would do differently.")
for tid, name, items in [
    ("hr_motivation", "Motivation & Career Goals", [
        (1, "Tell me about yourself and why you're interested in this role.", "Connect your past experience to what this role needs, then say why it excites you."),
        (2, "Where do you see yourself in three years, and how does this role help you get there?", "Be specific about skills you want to build, and link them to this job.")]),
    ("hr_teamwork", "Teamwork & Collaboration", [
        (1, "Describe a time you worked in a team to deliver something under a deadline.", "Use STAR: set the scene, then focus on what *you* did."),
        (2, "Tell me about a time you had to work with someone whose style was very different from yours.", "What did you adapt, and what was the result?")]),
    ("hr_conflict", "Conflict & Disagreement", [
        (2, "Tell me about a disagreement with a teammate or manager. How did you handle it?", "Show how you listened, what you proposed, and how it ended."),
        (3, "Describe a time you had to push back on a decision you believed was wrong.", "Show evidence-based persuasion, and what you did if you lost the argument.")]),
    ("hr_failure", "Failure & Learning", [
        (2, "Tell me about a time you failed or made a significant mistake.", "Own it, describe how you fixed it, and what changed afterwards."),
        (3, "Describe feedback you received that was hard to hear. What did you do with it?", "Show how you changed your behaviour, with a concrete example.")]),
    ("hr_pressure", "Pressure & Prioritisation", [
        (1, "How do you handle multiple deadlines at the same time?", "Give a real example of how you prioritised and communicated."),
        (3, "Tell me about a time priorities changed suddenly mid-project. What did you do?", "Show how you re-planned and kept stakeholders informed.")]),
    ("hr_leadership", "Ownership & Leadership", [
        (2, "Describe a time you took ownership of something outside your direct responsibilities.", "Why did you step in, and what changed because of it?"),
        (3, "Tell me about a time you influenced a group without having formal authority.", "How did you build agreement?")]),
]:
    t = topic(tid, name, "hr", "", HR_ACTIONS)
    for lvl, text, hint in items:
        q(t, lvl, text, STAR, hint)

# --------------------------------------------------------------------------- Project-based
PROJECT_ACTIONS = ("Write a one-page summary of your best project: problem, architecture, your role, results.",
                   "List three technical decisions you made and the alternatives you rejected.",
                   "Prepare one honest story about something that went wrong in the project.")
for tid, name, items in [
    ("project_overview", "Project Walkthrough", [
        (1, "Tell me about a project you're proud of. What problem did it solve, and what was your role?", "Problem → your role → how it works → result.")]),
    ("project_decisions", "Technical Decisions", [
        (2, "In one of your projects, what was the hardest technical decision you made, and what trade-offs did you consider?", "Name the alternatives you rejected and why.")]),
    ("project_challenges", "Challenges & Debugging", [
        (2, "What was the toughest bug or obstacle in your project, and how did you resolve it?", "Walk through how you found the root cause, not just the fix.")]),
    ("project_scaling", "Scaling & Improvement", [
        (3, "If your main project had to handle 100 times more users tomorrow, what would break first and how would you fix it?", "Think about database, server, caching and third-party limits.")]),
]:
    t = topic(tid, name, "project", "", PROJECT_ACTIONS)
    for lvl, text, hint in items:
        q(t, lvl, text, PROJECT, hint)

# --------------------------------------------------------------------------- Coding
CODE_ACTIONS = ("Before coding, state the brute-force approach and its complexity, then optimise.",
                "Always list edge cases (empty input, duplicates, negatives, very large input) before you finish.",
                "Practise 2 problems a day on this pattern and explain your solution out loud.")
COMPLEXITY = _c("time and space complexity", r"o\(|complexity|linear|constant|log")
EDGE = _c("edge cases", r"edge|empty|null|none|single|negative|duplicate|overflow|zero")
t = topic("coding_strings", "Coding: Strings", "coding", "", CODE_ACTIONS)
q(t, 1, "Write a function that checks whether a string is a palindrome, ignoring case and non-alphanumeric characters. Explain its complexity.",
  [_c("normalise: lowercase and filter characters", r"lower|isalnum|isalpha|regex|filter|clean|replace"),
   _c("compare from both ends (two pointers) or with the reversed string", r"two pointers|left|right|\[::-1\]|reverse|i < j|while"),
   COMPLEXITY, EDGE],
  "Clean the string first, then compare characters from both ends.")
q(t, 2, "Given a string, find the length of the longest substring without repeating characters.",
  [_c("sliding window with two pointers", r"sliding|window|two pointers|left|start"),
   _c("set or map of characters / last seen index", r"set|dict|map|last (seen|index)|hash"),
   COMPLEXITY, EDGE],
  "Grow a window to the right; when a character repeats, move the left edge.")
t = topic("coding_arrays", "Coding: Arrays & Hashing", "coding", "", CODE_ACTIONS)
q(t, 1, "Given an array of integers and a target, return the indices of two numbers that add up to the target.",
  [_c("hash map from value to index", r"hash|dict|map|seen"),
   _c("look up the complement (target - x)", r"complement|target ?- ?|difference"),
   COMPLEXITY, _c("brute force O(n²) comparison", r"brute|nested|n\^?2|n²|two loops")],
  "For each number, what value would you need to have already seen?")
q(t, 3, "Merge overlapping intervals, e.g. [[1,3],[2,6],[8,10]] → [[1,6],[8,10]].",
  [_c("sort by start time", r"sort"),
   _c("merge when the next start ≤ current end", r"overlap|end|max\(|<=|merge"),
   _c("O(n log n) because of sorting", r"n ?log ?n|sort"),
   EDGE],
  "Once intervals are sorted, when can two neighbours be merged?")
t = topic("coding_stacks", "Coding: Stacks & Queues", "coding", "", CODE_ACTIONS)
q(t, 2, "Check whether a string of brackets like \"{[()]}\" is balanced.",
  [_c("use a stack", r"stack|push|pop|append"),
   _c("match each closing bracket with the latest opening one", r"match|pair|map|closing|top"),
   _c("stack must be empty at the end", r"empty|len|left over|remaining"),
   COMPLEXITY],
  "Which open bracket must the next closing bracket match?")
t = topic("coding_design", "Coding: Data-Structure Design", "coding", "", CODE_ACTIONS)
q(t, 3, "Design an LRU cache that supports get and put in O(1) time.",
  [_c("hash map for O(1) lookup", r"hash|map|dict"),
   _c("doubly linked list for recency order", r"doubly|linked list|deque|order"),
   _c("move to front on access; evict least recently used at capacity", r"evict|remove (the )?(last|tail|oldest)|move to (front|head|end)|capacity"),
   _c("built-ins: OrderedDict / LinkedHashMap", r"ordereddict|linkedhashmap|move_to_end")],
  "You need fast lookup *and* fast reordering. Which two structures give you each?")

# --------------------------------------------------------------------------- Role mapping
ROLE_TOPICS: dict[str, list[str]] = {
    "java_developer": ["java_oop", "java_collections", "java_core", "java_concurrency", "java_jvm", "spring_boot", "databases", "dsa"],
    "python_developer": ["python_core", "python_advanced", "testing", "sql", "http_rest", "dsa", "databases"],
    "data_analyst": ["sql", "data_analysis", "statistics", "data_viz", "databases"],
    "web_developer": ["html_css", "javascript", "react", "http_rest", "testing", "system_design"],
    "software_engineer": ["dsa", "system_design", "databases", "http_rest", "testing", "sql"],
    "ml_engineer": ["ml_fundamentals", "ml_evaluation", "deep_learning", "ml_ops", "python_core", "statistics"],
}
ROLE_LABELS = {
    "java_developer": "Java Developer", "python_developer": "Python Developer", "data_analyst": "Data Analyst",
    "web_developer": "Web Developer", "software_engineer": "Software Engineer",
    "ml_engineer": "Machine Learning Engineer", "custom": "Custom Role",
}
HR_TOPICS = [k for k, v in T.items() if v.category == "hr"]
PROJECT_TOPICS = [k for k, v in T.items() if v.category == "project"]
CODING_TOPICS = [k for k, v in T.items() if v.category == "coding"]


def technical_topics_for_role(role: str, custom_role: str = "") -> list[str]:
    if role in ROLE_TOPICS:
        return list(ROLE_TOPICS[role])
    # Custom role: match the free-text role against topic names and keywords.
    text = (custom_role or role).lower()
    scored = []
    for tid, tp in T.items():
        if tp.category != "technical":
            continue
        hits = sum(1 for kw in tp.keywords if kw and kw in text) + (1 if tp.name.lower().split()[0] in text else 0)
        if hits:
            scored.append((hits, tid))
    scored.sort(reverse=True)
    picked = [tid for _, tid in scored[:6]]
    for tid in ROLE_TOPICS["software_engineer"]:
        if len(picked) >= 5:
            break
        if tid not in picked:
            picked.append(tid)
    return picked


def topics_for(role: str, interview_type: str, custom_role: str = "") -> list[str]:
    if interview_type == "hr":
        return list(HR_TOPICS)
    if interview_type == "project":
        return list(PROJECT_TOPICS)
    if interview_type == "coding":
        return list(CODING_TOPICS)
    tech = technical_topics_for_role(role, custom_role)
    if interview_type == "mixed":
        return tech + HR_TOPICS + PROJECT_TOPICS + CODING_TOPICS
    return tech


def topic_name(topic_id: str) -> str:
    if topic_id in T:
        return T[topic_id].name
    return topic_id.replace("_", " ").title()


def get_bank_question(qid: str | None) -> BankQuestion | None:
    if not qid:
        return None
    tid = qid.rsplit("_", 1)[0]
    tp = T.get(tid)
    if not tp:
        return None
    return next((x for x in tp.questions if x.id == qid), None)
