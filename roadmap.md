# Enhancement Roadmap

## 0. Resolve a nitpick about annotating processes for lookup

The DSL currently provides all the attribute parameters like duration=N etc. as arguments to the Process initializer.  This is sometimes required for predefined arguments that can be relevant to any process like duration, but sometimes I would like to provide simple freeform annotations in the DSL that can be used for library lookup.  The Process should be willing to store these annotations even if they are not valid initializer arguments so the library can search for the processes later.

> **Q0a:** What should the DSL syntax for freeform annotations look like?  Options range from
> a trailing `[key=val, key2=val2]` block on the output line, to a separate `@tag` syntax, to
> a second header line.  Do values need to be typed (int, float, string) or are all strings fine?

**A0a:** I would likely want to iterate on this a bit, but the trailing [key=val, key2=val2] is a good suggestion and we should start with that.

> **Q0a-followup:** Where exactly on the line does `[key=val]` appear?  The current record
> header is `<outputs> | <name>:` with inputs on the next line.  I'd assume the annotation
> block goes after the `:`, e.g. `2 iron | smelt: [tier=2]`.  Is that right, and does it
> coexist cleanly with the existing `duration=N` positional parameter (which I'd need to check
> in the parser)?  Also: auto-detect int/float values or start with everything-is-a-string for
> the first iteration?

I think we would use that line, yeah, same one as `smelt:` in your example, but let's say the annotations in square brackets would always come after real initializer parameters.  We should autodetect int/float values for sure, I anticipate many of these annotations being numeric and expecting to do filtering like "parameter is less than X"

>
> **Q0b:** Should annotations survive augmentation (item 1)?  E.g. if you annotate a process
> as `tier=2` and then apply an efficiency augment, should the augmented process inherit that
> annotation, possibly override it, or drop it?

**A0b:** Great question.  Augmented processes should inherit and possibly override annotations.

>
> **Q0c:** Is library lookup the only intended consumer, or do you also want annotations
> surfaced in `printable_analysis` output / the frontend?  That affects whether they need to
> live on `Process` itself or just in a library-side index.

**A0c:** I have not nailed down all the use cases here, but I anticipate wanting to use these annotations for cost evaluation, for example, so living on Process is likely safest and easiest to extend into future use cases.

## 1. Re-implement augment.py

The current implementation of augment.py sucks.  It introduces a gross wrapper class around Process with some hardcoded methods that are quite ad-hoc.  Using the AugmentedProcess manually is not really ergonomic (I previously just had some standard ones that were universally applied to every process so we didn't need to involve the ProcessLibrary), so they don't really even satisfy their primary design goals.

What we want is to be capable of modeling some standard transformations on processes that yield new processes within the DSL.  Any function Process -> Process could be acceptable as an "augmentation".  We need to be able to attach these augmentations to the ProcessLibrary for use in the DSL in a standard way.  We then need to be able to either manually apply these augmentations to processes in the DSL, or specify that we want to apply them to whole batches of processes.  This will involve some DSL extensions and likely a reimplementation of augment.py.

> **Q1a:** What augmentations do you actually use?  The current code has `increase_energy_pct`
> (hardcoded to kWe) and `scale`.  Is the real use case things like "add 10% kWe overhead to
> every process in the library" or "double throughput of process X"?  Knowing the concrete
> examples helps decide whether augmentations should be parameterised closures, named library
> entries, or something else.
>

**A1a:** Here are three qualitatively different types of augumentation that I use in practice.  They are from the game factorio, where you can have:

(1) multiple different tiers of assembler, which are ultimately processes with different output rates and different energy consumption.  Every recipe in the input should have a variant for each assembler type.

(2) addition of speed, production, or efficiency modules, which can be mixed-and-matched and each provides some sort of buff and debuff to assembler production parameters (rate, power consumption, possible input rate attenuation).  Since there are so many possible combinations, I would want to apply these in the DSL to the recipes of relevance only when I think I need to do a certain optimization.

(3) the presence of global productivity or speed buffs, which would apply across all recipes, but only represents a single global modification (unlike the assembler tiers which require multiple recipe variants be listed, this essentially replaces all recipes with variants modified in the same way)

> **Q1b:** Should augmentations be composable/chainable in the DSL (e.g. apply efficiency then
> scale), or is a single augmentation per process/group sufficient for now?
>

**A1b:** Composability is essential, though we can approach this iteratively and start with a single augmentation per process/group

> **Q1c:** When an augmentation is applied to a *batch* of processes (e.g. all processes with
> annotation `tier=2`), should it produce *new* named library entries alongside the originals,
> *replace* them, or produce a separate "augmented view" of the library?  This choice has big
> implications for how `production_graphs` sees the augmented processes.
>

**A1c:** It should produce new named library entries.  There are cases like example (3) in answer A1a above, where conceptually it seems like the recipes are being replaced, but really I would rather represent this as new library entries

> **Q1d:** Should augmented processes be eligible as inputs to further augmentation, or is one
> level of augmentation the intended ceiling?

**A1d:** Since augmentations should be composable I think allowing augmentation of augmented processes is the cleanest way forward-- ideally augmented processes would just be processes but with some metadata attached that remembers what augmentations have been applied.  Perhaps processes can be regarded as augmented processes with no applied augmentations.

> **Q1e:** How are augmentations *defined*?  Because they're `Process -> Process` transforms,
> they can't be expressed purely in DSL text without a fixed vocabulary of transform types.
> I see two options:
> (a) a small set of built-in named transforms (e.g. `scale(rate=1.5)`,
>     `add_energy(kind="kWe", pct=0.1)`) that the DSL references by name+params, and the
>     library knows how to construct from those names; or
> (b) Python callables registered with the library by name before parsing, then referenced
>     by name in the DSL.
> Option (a) keeps everything in the DSL but limits extensibility; option (b) is fully
> general but requires Python-side setup before DSL parsing.  Which do you prefer, or is a
> hybrid (built-ins plus a register hook) the right answer?
>

I really prefer option (b) since the augmentations can truly be arbitrary.  The existing library is naive.

> **Q1f:** How is an augmentation *applied* in the DSL?  E.g., is the syntax something like
> `apply assembler_mk2 to [tier=1]` on its own line, or is it expressed differently?  And
> is "apply to all" just `apply assembler_mk2 to *`?
>

We'll need to iterate on this, but I'm thinking we can apply to individual recipes with `@` annotations like `@assembler_mk2 @speed_mod_mk2` on the same line as the process name `process_name:`, apply to "all subsequent recipes" by putting the annotations on their own line, apply a product of annotations by having multiple lines, e.g.
```
@assembler_mk1
@assembler_mk2
@assembler_mk3 @speed_mod_mk3

recipe1 = in1 + in2

recipe2 = in4 + 2 in5
```

> **Q1g:** Naming of augmented entries.  When augmenting produces new library entries, what
> are their names?  Options: auto-generated suffix (e.g. `"iron via smelt [assembler_mk2]"`),
> a naming scheme baked into the augmentation definition, or user-specified.  Auto-generation
> is convenient but the names need to remain stable for `visited`-set deduplication in
> `_production_graphs` to work correctly.
>

Yeah adding them in square brackets and sorting them alphabetically when there are multiple is a good solution for naming.

> **Q1h (Factorio case 1):** For assembler tiers — after augmentation, should
> `production_graphs` see *both* the original (tier=1) and the new (tier=2) entry as
> candidates simultaneously?  If so, the search space for a library with N recipes and M tiers
> grows by M× per process depth, which can be a lot.  Or do you filter the library to a single
> tier before calling `production_graphs`, and the point of generating the augmented entries is
> just to make it easy to switch between tiers?

I think we should add all the entries to the library, but similar to how we have stop_kinds and skip_processes we can have something like only_augments or skip_augments or something.  We could also stand to improve this "pre-filtering" specification at some point.


## 2. Find a way to mix batch and continuous processes in a graph

Currently the processes must either all be batch or continuous in a graph, and it's implicit which is in use.  If callers use transfer rates instead of transfer that basically is what determines the disposition.

I would like a way to express _a priori_ that a process is batch or continuous (perhaps the presence or absence of a duration field is sufficient), and to have the graph resolve this: continuous processes can run in parallel, but they require their inputs are available before they can start.  Therefore the graphs consist of "concurrent combinations of batches" or "batches of concurrent combinations" nested arbitrarily.

It should still be possible to calculate process depths so the order in which processes are performed can be emitted to the user.

This actually sounds pretty difficult so this might be a multi-stage project.

> **Q2a:** Is "presence/absence of `duration`" the intended discriminator, or do you want an
> explicit `mode=batch|continuous` field?  Using duration as a proxy is convenient but means a
> process can't be batch *and* have a duration (which might be useful for reporting cycle time).
>

**A2a:** You're right, a mode switch is a better idea because cycle time could be helpful for cost sorting.  Let's go with that.

> **Q2b:** I want to make sure I understand the mixed semantics correctly.  My reading: a
> *continuous* process runs at a steady rate and can be paired with other continuous processes
> that share a pool (they just balance flows).  A *batch* process runs N integer times and
> produces/consumes discrete lumps.  When a batch output feeds a continuous input, the solver
> must ensure the batch throughput (count × transfer) satisfies the continuous demand rate.
> Is that the right mental model, or is the relationship between the two modes different?
>

**A2b:** This is close.  Continuous processes can be grouped into a single batch which draw from the same SET of pools as other continuous processes in the batch.  They should balance their input and output rates to reduce wasteage as usual.  Batch processes must run N times until they have produced at least the total volume of inputs necessary for the next downstream batch process.

Combining them is subtle, as you have noticed, and I don't have a full design.  I will need to spitball this with you.

Ultimately what I want is for the user to request EITHER an output rate or an output quantity.  If they need a quantity, then continuous processes should run in parallel for as long as necessary to produce enough volume to meet the desired demand quantity.  This demand could come directly from the user's request, or from downstream batch processes (or downstream groups of continuous processes that run as a batch, i.e. which do not require any batch processes to provide them with inputs).  If the user demands a rate, then I suppose they must also provide "how long do you need to keep this rate going", and this will translate to output rates from groups of parallel continuous processes, and input "buffer" volumes from batches that will ensure the graph is not starved for inputs for that duration.

> **Q2c:** Does the "nesting" (batches of concurrent combinations vs. concurrent combinations
> of batches) always resolve to exactly two levels, or is truly arbitrary depth needed?
> Arbitrary depth would require a recursive graph structure, which is a substantially bigger
> lift than a two-level model.
>

**A2c:** I would be surprised if it resolved to exactly two levels in all cases, so I do think this is gonna be some arbitrary recursive graph structure, which is why I worry this will be hard.  In fact I might swap this roadmap entry with the cost function entry because that is probably easier.

> **Q2d:** For the MILP: continuous processes currently contribute real-valued rates; batch
> processes contribute integer counts.  A mixed graph would require a mixed-integer program
> with both integer and real variables.  scipy's `milp` supports this.  Are you comfortable
> accepting the increased solver complexity, or would you prefer to keep the two modes
> independent (solve batch and continuous sub-graphs separately and stitch outputs)?

**A2d:** Yeah I require that x in A x = b has integer entries, but A and b will generally have real numbers.  This is supported by milp and I have already used this with some success with graphs made only of continuous processes.


## 3. Sort graph results by an arbitrary "cost" function

It happens frequently that there are quite a few ways to produce something, and many different reasons why some methods may be preferred over others.  I would therefore like to add the ability to evaluate some (scalar) function on a graph and sort the output on the function value.  Examples of this could be minimizing raw ingredient cost, or minimizing total process time, or minimizing total number of processes, or maximizing profit compared with some reference price.

Ideally we would be able to do like a lazy `topk` evaluation rather than a brute-force "load all possible graphs into memory and sort them".

> **Q3a:** Should cost operate on the *unsolved* graph structure (topology only), the *solved*
> graph (after MILP, so process counts are available), or both?  Many natural costs (total
> ingredient volume, total process time) need counts, but solving every candidate graph before
> sorting would be expensive if there are hundreds of graphs.
>

**A3a:** I do actually need this to operate on the solved graphs, so yes this could be expensive, which is why I'd like to try for lazy top-k if possible.

> **Q3b:** For lazy top-k: `production_graphs` is currently a depth-first generator with no
> natural cost-monotone ordering.  True lazy top-k needs either a priority-queue-based
> best-first search or an admissible heuristic to prune branches early.  How important is the
> lazy property vs. just computing all graphs up front and sorting?  For typical game crafting
> libraries (tens to low hundreds of graphs) the brute-force approach is probably fine; lazy
> matters mainly if graph counts can reach thousands.
>

**A3b:** Hmmm, yeah I was really hoping lazy was possible, but with an arbitrary cost function it does seem generally impossible to ensure the traversal is monotone, so we may be screwed here and need to evaluate the graphs.  It's true that these sizes will not be completely enormous, but as processes produce more outputs and more processes produce duplicate outputs, the number of candidate graphs grows exponentially.  I guess it would be best to just start with brute-force for now and see where we can optimize later.

> **Q3c:** What is the primary cost function you have in mind for your first use case?  If it's
> something simple like "fewest total processes" or "cheapest raw ingredients given a price
> table", we can design the interface around that and generalise later.
>

**A3c:** The primary one will be cheapest raw ingredients given a price table

> **Q3d:** Should the cost function be provided as a Python callable at call time (most
> flexible), registered in the library (so it can be named and reused in the DSL), or both?

**A3d:** We can start with it as a callable at call time.  We may only have a few of these, so arbitrary library support may not be necessary.

> **Q3e:** What argument(s) does the cost callable receive?  For the primary "cheapest raw
> ingredients" case, the function needs at minimum the raw inputs (kinds + amounts) — that's
> the `transfer` Ingredients object already on the `analyze_graph` result dict.  But other
> cost functions (e.g. total process time) also need per-process counts.  The safest signature
> is `cost_fn(analysis_result: dict) -> float` where `analysis_result` is one item from
> `analyze_graph`, since it already carries `transfer`, `inputs`, `sorted_process_counts`,
> and `total_processes`.  Does that work, or do you need access to the raw `GraphBuilder` as
> well (e.g. to traverse pool structure)?
>

Great point.  We probably do need both.  For example there could be a situation where we might want to evaluate the costs of intermediate products, which would require looking at the graph.

> **Q3f:** Should cost-sorted output be a new entry point (e.g. `best_k_graphs(graphs,
> cost_fn, k)` returning a list), or should `analyze_graphs` / `production_graphs` grow an
> optional `cost_fn` parameter that reorders their output?  The former is a pure add-on with
> no API churn; the latter is cleaner to call but requires buffering all graphs before yielding
> anything, which changes the generator semantics.

The former is the way to go here, I want to keep the option open for iterating through with less memory cost but without ordering guarantees.


## 4. Recheck integrations with crafting_frontend

There is a basic web app wrapper around this that I use, and I would like to re-evaluate its integrations with this repo so that we can enhance the frontend as well.

> **Q4a:** What does the current integration surface look like — does the frontend call
> `production_graphs` + `printable_analysis` directly, or does it go through a separate API
> layer?  (I can read the frontend code when we get to this item, but a quick summary of the
> current seam would help me flag which roadmap items above are most likely to break it.)
>

**A4a:** Let's come back to this in the future, but I can simply show you the frontend code when the time comes.

> **Q4b:** Are there known gaps in the frontend that motivated any of items 1–3 above, or is
> the frontend work largely independent?  Knowing this might affect sequencing.

**A4b:** Let's come back to this frontend in the future.

