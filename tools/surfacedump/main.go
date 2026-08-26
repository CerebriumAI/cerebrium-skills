// Command surfacedump prints the Cerebrium CLI surface as JSON.
//
// It is copied into a checkout of CerebriumAI/cerebrium at run time, executed
// there, and discarded. It is never committed to that repository and it never
// modifies go.mod or go.sum: cobra and pflag are already required by that
// module, and a package inside the module may import internal/... .
//
// The surface is read by reflecting over the real cobra tree and the real
// cerebrium.toml config struct. Parsing `--help` output was tried and rejected:
// cobra pads the command-name column to the longest command name, so a
// two-space split silently drops `save-auth-config`. That is column arithmetic,
// not a fact about the CLI.
//
// Usage:
//
//	go run ./skilldrift/surfacedump > surface.json
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"reflect"
	"sort"
	"strconv"
	"strings"

	"github.com/cerebriumai/cerebrium/internal/commands"
	"github.com/cerebriumai/cerebrium/pkg/projectconfig"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

// Flag is one pflag definition.
type Flag struct {
	Name      string `json:"name"`
	Shorthand string `json:"shorthand,omitempty"`
	Usage     string `json:"usage"`
	Default   string `json:"default,omitempty"`
	Hidden    bool   `json:"hidden,omitempty"`
}

// Command is one node of the cobra tree. Path excludes the binary name, so the
// root is "" and `cerebrium apps get` is "apps get".
type Command struct {
	Path      string   `json:"path"`
	Aliases   []string `json:"aliases,omitempty"`
	Hidden    bool     `json:"hidden,omitempty"`
	Runnable  bool     `json:"runnable"`
	Flags     []Flag   `json:"flags"`
	Inherited []string `json:"inherited,omitempty"`
	// UnknownFlagsOK is cobra's FParseErrWhitelist. `cerebrium run` sets it so
	// that any --key value pair is passed through to the function being run,
	// which means an undeclared flag there is not a documentation error.
	UnknownFlagsOK bool `json:"unknown_flags_ok,omitempty"`
}

// Section is one cerebrium.toml table and the keys the CLI parses from it.
type Section struct {
	Section  string   `json:"section"`
	Keys     []string `json:"keys"`
	FreeForm bool     `json:"free_form,omitempty"`
}

// Surface is the whole extracted surface.
type Surface struct {
	Binary          string    `json:"binary"`
	GlobalFlags     []Flag    `json:"global_flags"`
	Commands        []Command `json:"commands"`
	ConfigSections  []Section `json:"config_sections"`
	RawTOMLUploaded bool      `json:"raw_toml_uploaded"`
}

// configSectionForField maps a ProjectConfig field to the cerebrium.toml table
// the loader reads it from. The struct tags do not carry the full path, so this
// mapping is explicit and an unmapped field is a hard error: a new section can
// never be dropped in silence. "@partner" expands to one table per partner
// service, "@ignore" is a field that is not a TOML key, and "section:key" is a
// scalar key rather than a table of its own.
var configSectionForField = map[string]string{
	"Deployment":       "cerebrium.deployment",
	"Hardware":         "cerebrium.hardware",
	"Scaling":          "cerebrium.scaling",
	"Dependencies":     "cerebrium.dependencies",
	"CustomRuntime":    "cerebrium.runtime.custom",
	"PartnerService":   "@partner",
	"ContainerRuntime": "cerebrium.runtime:container_runtime",
	"RawTOML":          "@ignore",
}

func main() {
	loaderPath := flag.String("loader", "pkg/projectconfig/loader.go",
		"path to the cerebrium.toml loader, read for the partner service table names")
	flag.Parse()

	partnerNames, partnerKeys, viperKeys, err := readLoader(*loaderPath)
	if err != nil {
		fatal(err)
	}

	sections, err := configSections(partnerNames, partnerKeys, viperKeys)
	if err != nil {
		fatal(err)
	}

	root := commands.NewRootCmd()
	surface := Surface{
		Binary:          root.Name(),
		GlobalFlags:     flagSet(root.PersistentFlags()),
		Commands:        walk(root, ""),
		ConfigSections:  sections,
		RawTOMLUploaded: hasField(reflect.TypeOf(projectconfig.ProjectConfig{}), "RawTOML"),
	}

	out := json.NewEncoder(os.Stdout)
	out.SetIndent("", "  ")
	if err := out.Encode(surface); err != nil {
		fatal(err)
	}
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "surfacedump:", err)
	os.Exit(1)
}

// walk returns the command and every descendant, depth first.
func walk(cmd *cobra.Command, prefix string) []Command {
	path := strings.TrimSpace(prefix + " " + cmd.Name())
	if cmd.HasParent() == false {
		path = ""
	}

	node := Command{
		Path:           path,
		Aliases:        cmd.Aliases,
		Hidden:         cmd.Hidden,
		Runnable:       cmd.Runnable(),
		Flags:          flagSet(cmd.LocalFlags()),
		Inherited:      flagNames(cmd.InheritedFlags()),
		UnknownFlagsOK: cmd.FParseErrWhitelist.UnknownFlags,
	}
	out := []Command{node}
	for _, child := range cmd.Commands() {
		out = append(out, walk(child, path)...)
	}
	return out
}

func flagSet(fs *pflag.FlagSet) []Flag {
	var out []Flag
	fs.VisitAll(func(f *pflag.Flag) {
		if f.Name == "help" {
			return // cobra adds this to every command
		}
		out = append(out, Flag{
			Name:      f.Name,
			Shorthand: f.Shorthand,
			Usage:     f.Usage,
			Default:   f.DefValue,
			Hidden:    f.Hidden,
		})
	})
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func flagNames(fs *pflag.FlagSet) []string {
	var out []string
	fs.VisitAll(func(f *pflag.Flag) {
		if f.Name != "help" {
			out = append(out, f.Name)
		}
	})
	sort.Strings(out)
	return out
}

// configSections reflects ProjectConfig into one entry per cerebrium.toml
// table. Only the top level is reflected: the keys of a table are the fields of
// the struct the loader unmarshals into it.
func configSections(partnerNames, partnerKeys, viperKeys []string) ([]Section, error) {
	byName := map[string]*Section{}
	order := []string{}
	// Partner tables are named by the loader through fmt.Sprintf, so they never
	// appear as a literal and are exempt from the staleness guard below. They
	// were read out of the loader source in the first place.
	fromLiteral := map[string]bool{}
	add := func(name string, keys []string, freeForm bool) {
		s, ok := byName[name]
		if !ok {
			s = &Section{Section: name, FreeForm: freeForm}
			byName[name] = s
			order = append(order, name)
		}
		s.Keys = append(s.Keys, keys...)
	}

	t := reflect.TypeOf(projectconfig.ProjectConfig{})
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		target, ok := configSectionForField[field.Name]
		if !ok {
			return nil, fmt.Errorf("ProjectConfig field %q has no cerebrium.toml table mapping; "+
				"add it to configSectionForField", field.Name)
		}
		switch {
		case target == "@ignore":
		case target == "@partner":
			for _, partner := range partnerNames {
				add("cerebrium.runtime."+partner, partnerKeys, false)
			}
		case strings.Contains(target, ":"):
			parts := strings.SplitN(target, ":", 2)
			add(parts[0], []string{parts[1]}, false)
			fromLiteral[parts[0]] = true
		default:
			keys, freeForm := structKeys(field.Type)
			add(target, keys, freeForm)
			fromLiteral[target] = true
		}
	}

	// Guard against a renamed table: every mapped path must still appear as, or
	// as the prefix of, a viper key the loader actually reads.
	for _, name := range order {
		if !fromLiteral[name] {
			continue
		}
		found := false
		for _, key := range viperKeys {
			if key == name || strings.HasPrefix(key, name+".") {
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("table %q is not read by the loader; configSectionForField is stale", name)
		}
	}

	out := make([]Section, 0, len(order))
	for _, name := range order {
		s := byName[name]
		sort.Strings(s.Keys)
		out = append(out, *s)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Section < out[j].Section })
	return out, nil
}

// structKeys returns the mapstructure keys of a struct type. A map type has no
// fixed keys, which it reports as free form.
func structKeys(t reflect.Type) ([]string, bool) {
	for t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	if t.Kind() == reflect.Map {
		return nil, true
	}
	if t.Kind() != reflect.Struct {
		return nil, true
	}
	var keys []string
	for i := 0; i < t.NumField(); i++ {
		tag := t.Field(i).Tag.Get("mapstructure")
		name := strings.Split(tag, ",")[0]
		if name == "" || name == "-" {
			continue
		}
		keys = append(keys, name)
	}
	return keys, false
}

func hasField(t reflect.Type, name string) bool {
	_, ok := t.FieldByName(name)
	return ok
}

// readLoader extracts three things from the config loader source:
//
//   - the partner service names, from the `partnerNames` slice literal;
//   - the keys read inside the loop over those names, from the `key + ".port"`
//     style expressions, so the reported keys are the ones the loader actually
//     reads rather than every field on the struct;
//   - every "cerebrium.*" viper key, used to check the table mapping is current.
func readLoader(path string) (partnerNames, partnerKeys, viperKeys []string, err error) {
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, path, nil, 0)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("parsing %s: %w", path, err)
	}

	ast.Inspect(file, func(n ast.Node) bool {
		if lit, ok := n.(*ast.BasicLit); ok && lit.Kind == token.STRING {
			if s, err := strconv.Unquote(lit.Value); err == nil && strings.HasPrefix(s, "cerebrium.") {
				viperKeys = append(viperKeys, s)
			}
		}
		assign, ok := n.(*ast.AssignStmt)
		if !ok || len(assign.Lhs) != 1 || len(assign.Rhs) != 1 {
			return true
		}
		ident, ok := assign.Lhs[0].(*ast.Ident)
		if !ok || ident.Name != "partnerNames" {
			return true
		}
		composite, ok := assign.Rhs[0].(*ast.CompositeLit)
		if !ok {
			return true
		}
		for _, elt := range composite.Elts {
			if lit, ok := elt.(*ast.BasicLit); ok && lit.Kind == token.STRING {
				if s, err := strconv.Unquote(lit.Value); err == nil {
					partnerNames = append(partnerNames, s)
				}
			}
		}
		return true
	})

	ast.Inspect(file, func(n ast.Node) bool {
		rng, ok := n.(*ast.RangeStmt)
		if !ok {
			return true
		}
		if ident, ok := rng.X.(*ast.Ident); !ok || ident.Name != "partnerNames" {
			return true
		}
		seen := map[string]bool{}
		ast.Inspect(rng.Body, func(inner ast.Node) bool {
			bin, ok := inner.(*ast.BinaryExpr)
			if !ok || bin.Op != token.ADD {
				return true
			}
			lit, ok := bin.Y.(*ast.BasicLit)
			if !ok || lit.Kind != token.STRING {
				return true
			}
			s, err := strconv.Unquote(lit.Value)
			if err != nil || !strings.HasPrefix(s, ".") {
				return true
			}
			key := strings.TrimPrefix(s, ".")
			if key != "" && !seen[key] {
				seen[key] = true
				partnerKeys = append(partnerKeys, key)
			}
			return true
		})
		return false
	})

	if len(partnerNames) == 0 {
		return nil, nil, nil, fmt.Errorf("no partnerNames literal found in %s", path)
	}
	if len(partnerKeys) == 0 {
		return nil, nil, nil, fmt.Errorf("no partner service keys found in the partnerNames loop in %s", path)
	}
	sort.Strings(partnerKeys)
	return partnerNames, partnerKeys, viperKeys, nil
}
