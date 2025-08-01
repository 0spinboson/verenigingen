#!/usr/bin/env python3
"""
Schema-Aware Context-Intelligent Field Validator

A next-generation field validator that addresses the 99.9% false positive rate by:
1. Reading actual database schema including custom fields
2. Understanding code context and variable scoping
3. Supporting all valid Frappe ORM patterns
4. Providing intelligent pattern recognition

Architectural Components:
- DatabaseSchemaReader: Dynamic schema introspection
- ContextAnalyzer: Intelligent code context parsing
- FrappePatternHandler: Support for all valid Frappe patterns
- ValidationEngine: Core validation logic with confidence scoring
"""

import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass, field
from collections import defaultdict
import sys
import os


@dataclass
class ValidationIssue:
    """Represents a field validation issue with confidence scoring"""
    file_path: str
    line_number: int
    obj_name: str
    field_name: str
    doctype: str
    issue_type: str
    message: str
    context: str
    confidence: float  # 0.0 to 1.0 (1.0 = definitely an error)
    suggestion: Optional[str] = None
    pattern_matched: Optional[str] = None


@dataclass
class DocTypeSchema:
    """Complete schema information for a DocType"""
    name: str
    fields: Dict[str, Dict[str, Any]]  # field_name -> field_info
    custom_fields: Dict[str, Dict[str, Any]]  # custom field definitions
    child_tables: Dict[str, str]  # child_table_field -> target_doctype
    parent_doctype: Optional[str] = None  # for child tables
    is_child_table: bool = False


@dataclass 
class CodeContext:
    """Represents the context of a code location"""
    variable_assignments: Dict[str, str]  # var_name -> inferred_type
    sql_variables: Set[str]  # variables that hold SQL results
    child_table_iterations: Dict[str, str]  # var_name -> child_doctype
    property_methods: Set[str]  # known @property methods
    frappe_api_calls: Set[str]  # variables from frappe API calls
    function_context: Optional[str] = None  # current function name
    class_context: Optional[str] = None  # current class name


class DatabaseSchemaReader:
    """Reads actual database schema including custom fields"""
    
    def __init__(self, app_path: str):
        self.app_path = Path(app_path)
        self.doctypes = {}
        self.custom_fields_cache = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all DocType schemas including custom fields"""
        # Load static DocType definitions
        doctype_dir = self.app_path / "verenigingen" / "verenigingen" / "doctype"
        
        for doctype_path in doctype_dir.iterdir():
            if doctype_path.is_dir():
                json_file = doctype_path / f"{doctype_path.name}.json"
                if json_file.exists():
                    schema = self._load_doctype_schema(json_file)
                    if schema:
                        self.doctypes[schema.name] = schema
        
        # Load custom fields from fixtures if available
        self._load_custom_fields()
        
        print(f"📋 Loaded {len(self.doctypes)} DocType schemas")
    
    def _load_doctype_schema(self, json_file: Path) -> Optional[DocTypeSchema]:
        """Load a single DocType schema"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            schema = DocTypeSchema(
                name=data.get('name', ''),
                fields={},
                custom_fields={},
                child_tables={},
                is_child_table=data.get('istable', 0) == 1
            )
            
            # Process fields
            for field_data in data.get('fields', []):
                field_name = field_data.get('fieldname')
                if field_name:
                    schema.fields[field_name] = field_data
                    
                    # Track child table relationships
                    if field_data.get('fieldtype') == 'Table':
                        options = field_data.get('options')
                        if options:
                            schema.child_tables[field_name] = options
            
            return schema
            
        except Exception as e:
            print(f"⚠️  Error loading {json_file}: {e}")
            return None
    
    def _load_custom_fields(self):
        """Load custom field definitions from fixtures"""
        fixtures_dir = self.app_path / "verenigingen" / "fixtures"
        
        # Look for custom field fixtures
        for fixture_file in fixtures_dir.glob("*.json"):
            try:
                with open(fixture_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Process custom field data
                if isinstance(data, list):
                    for item in data:
                        if item.get('doctype') == 'Custom Field':
                            dt = item.get('dt')
                            fieldname = item.get('fieldname')
                            if dt and fieldname and dt in self.doctypes:
                                self.doctypes[dt].custom_fields[fieldname] = item
                                
            except Exception:
                continue
    
    def get_field_info(self, doctype: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Get field information including custom fields"""
        if doctype not in self.doctypes:
            return None
            
        schema = self.doctypes[doctype]
        
        # Check standard fields first
        if field_name in schema.fields:
            return schema.fields[field_name]
        
        # Check custom fields
        if field_name in schema.custom_fields:
            return schema.custom_fields[field_name]
            
        return None
    
    def is_valid_field(self, doctype: str, field_name: str) -> bool:
        """Check if field exists in DocType schema"""
        return self.get_field_info(doctype, field_name) is not None
    
    def get_child_table_doctype(self, parent_doctype: str, child_field: str) -> Optional[str]:
        """Get the DocType of a child table field"""
        if parent_doctype in self.doctypes:
            return self.doctypes[parent_doctype].child_tables.get(child_field)
        return None


class ContextAnalyzer:
    """Analyzes code context to understand variable types and scoping"""
    
    def __init__(self, schema_reader: DatabaseSchemaReader):
        self.schema_reader = schema_reader
        self.builtin_patterns = self._build_builtin_patterns()
    
    def _build_builtin_patterns(self) -> Dict[str, Set[str]]:
        """Build patterns for built-in Python and Frappe objects"""
        return {
            'python_builtins': {
                'dict', 'list', 'str', 'int', 'float', 'bool', 'set', 'tuple',
                'datetime', 'date', 'time', 'json', 'request', 'response'
            },
            'frappe_objects': {
                'frappe', 'form_dict', 'local', 'cache', 'session', 'user',
                'db', 'utils', 'model', 'defaults'
            },
            'sql_result_indicators': {
                'as_dict=True', 'frappe.db.sql', 'frappe.db.get_all', 
                'frappe.db.get_list', 'frappe.db.get_value'
            }
        }
    
    def analyze_file_context(self, file_path: Path) -> Dict[int, CodeContext]:
        """Analyze entire file to build context for each line"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse AST for deep analysis
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                # Fallback to regex-based analysis for files with syntax errors
                return self._fallback_context_analysis(lines)
            
            return self._analyze_ast_context(tree, lines)
            
        except Exception as e:
            print(f"⚠️  Error analyzing context for {file_path}: {e}")
            return {}
    
    def _analyze_ast_context(self, tree: ast.AST, lines: List[str]) -> Dict[int, CodeContext]:
        """Analyze AST to build comprehensive context"""
        contexts = defaultdict(lambda: CodeContext(
            variable_assignments={},
            sql_variables=set(),
            child_table_iterations={},
            property_methods=set(),
            frappe_api_calls=set()
        ))
        
        class ContextVisitor(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.current_function = None
                self.current_class = None
                self.global_assignments = {}
                self.sql_variables = set()
                self.property_methods = set()
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                
                # Check for @property decorator
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Name) and decorator.id == 'property'):
                        self.property_methods.add(node.name)
                
                self.generic_visit(node)
                self.current_function = old_function
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_Assign(self, node):
                """Track variable assignments"""
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    var_name = node.targets[0].id
                    
                    # Analyze the value to determine type
                    var_type = self._infer_assignment_type(node.value)
                    
                    # Update contexts for affected lines
                    start_line = node.lineno
                    for line_num in range(start_line, len(lines) + 1):
                        contexts[line_num].variable_assignments[var_name] = var_type
                        
                        # Track SQL result variables
                        if 'sql_result' in var_type:
                            contexts[line_num].sql_variables.add(var_name)
                        
                        # Track Frappe API result variables
                        if 'frappe_api' in var_type:
                            contexts[line_num].frappe_api_calls.add(var_name)
                
                self.generic_visit(node)
            
            def visit_For(self, node):
                """Track for loop iterations, especially child table iterations"""
                if isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Attribute):
                    iter_var = node.target.id
                    
                    # Check if this is child table iteration
                    if isinstance(node.iter.value, ast.Name):
                        parent_var = node.iter.value.id
                        child_field = node.iter.attr
                        
                        # Try to determine if this is a child table
                        parent_type = self.global_assignments.get(parent_var, 'unknown')
                        if parent_type in self.analyzer.schema_reader.doctypes:
                            child_doctype = self.analyzer.schema_reader.get_child_table_doctype(
                                parent_type, child_field
                            )
                            if child_doctype:
                                # Update contexts within the loop scope
                                for line_num in range(node.lineno, node.end_lineno or len(lines)):
                                    contexts[line_num].child_table_iterations[iter_var] = child_doctype
                
                self.generic_visit(node)
            
            def _infer_assignment_type(self, value_node) -> str:
                """Infer the type of an assignment"""
                if isinstance(value_node, ast.Call):
                    if isinstance(value_node.func, ast.Attribute):
                        # frappe.db.sql, frappe.get_doc, etc.
                        if (isinstance(value_node.func.value, ast.Attribute) and
                            isinstance(value_node.func.value.value, ast.Name) and
                            value_node.func.value.value.id == 'frappe' and
                            value_node.func.value.attr == 'db'):
                            # Check for as_dict parameter
                            for keyword in value_node.keywords:
                                if keyword.arg == 'as_dict' and isinstance(keyword.value, ast.Constant):
                                    if keyword.value.value:
                                        return 'sql_result_dict'
                            return 'sql_result'
                        
                        elif (isinstance(value_node.func.value, ast.Name) and
                              value_node.func.value.id == 'frappe'):
                            func_name = value_node.func.attr
                            if func_name in ['get_doc', 'new_doc']:
                                # Try to extract DocType from first argument
                                if value_node.args and isinstance(value_node.args[0], ast.Constant):
                                    return value_node.args[0].value  # DocType name
                            elif func_name in ['get_all', 'get_list']:
                                return 'frappe_api_result'
                
                return 'unknown'
        
        visitor = ContextVisitor(self)
        visitor.visit(tree)
        
        # Propagate property methods to all contexts
        for line_num in contexts:
            contexts[line_num].property_methods = visitor.property_methods
        
        return dict(contexts)
    
    def _fallback_context_analysis(self, lines: List[str]) -> Dict[int, CodeContext]:
        """Fallback regex-based context analysis"""
        contexts = {}
        sql_variables = set()
        property_methods = set()
        
        for i, line in enumerate(lines):
            context = CodeContext(
                variable_assignments={},
                sql_variables=sql_variables.copy(),
                child_table_iterations={},
                property_methods=property_methods.copy(),
                frappe_api_calls=set()
            )
            
            # Track SQL result assignments
            if 'frappe.db.sql' in line and 'as_dict=True' in line:
                # Extract variable name
                match = re.search(r'(\w+)\s*=.*frappe\.db\.sql', line)
                if match:
                    sql_variables.add(match.group(1))
            
            # Track @property methods
            if '@property' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                prop_match = re.search(r'def\s+(\w+)\s*\(', next_line)
                if prop_match:
                    property_methods.add(prop_match.group(1))
            
            contexts[i + 1] = context
        
        return contexts


class FrappePatternHandler:
    """Handles all valid Frappe ORM patterns"""
    
    def __init__(self):
        self.valid_patterns = self._build_valid_patterns()
    
    def _build_valid_patterns(self) -> Dict[str, List[str]]:
        """Build comprehensive list of valid Frappe patterns"""
        return {
            'wildcards': [
                r'\*',  # SELECT * patterns
                r'frappe\.db\.get_all\([^)]*fields\s*=\s*\[\s*\*\s*\]',
            ],
            'aliases': [
                r'SELECT.*\s+as\s+\w+',
                r'frappe\.db\.sql\([^)]*\s+as\s+\w+',
            ],
            'child_table_access': [
                r'for\s+\w+\s+in\s+\w+\.\w+:',
                r'\w+\.\w+\[\d+\]\.\w+',  # indexed access
            ],
            'sql_functions': [
                r'COUNT\(', r'SUM\(', r'AVG\(', r'MIN\(', r'MAX\(',
                r'GROUP_CONCAT\(', r'CONCAT\(', r'DATE\(', r'NOW\('
            ],
            'frappe_api_patterns': [
                r'frappe\.get_all\([^)]*fields\s*=\s*\[.*\]',
                r'frappe\.db\.get_value\([^)]*fieldname\s*=',
                r'frappe\.db\.get_list\([^)]*fields\s*=',
            ],
            'meta_field_access': [
                r'\w+\.meta\.\w+',  # DocType meta access
                r'frappe\.get_meta\([^)]*\)\.\w+',
            ]
        }
    
    def is_valid_frappe_pattern(self, field_access: str, context: str) -> Tuple[bool, Optional[str]]:
        """Check if field access matches a valid Frappe pattern"""
        for pattern_type, patterns in self.valid_patterns.items():
            for pattern in patterns:
                if re.search(pattern, context, re.IGNORECASE):
                    return True, pattern_type
        
        return False, None
    
    def handle_wildcard_access(self, field_name: str, context: str) -> bool:
        """Handle wildcard field access patterns"""
        if field_name == '*':
            return True
        
        # Check if field is accessed in a wildcard context
        wildcard_indicators = [
            'SELECT *', 'fields=["*"]', 'fields=[\'*\']', 
            'get_all(*', 'as_dict=True'
        ]
        
        for indicator in wildcard_indicators:
            if indicator in context:
                return True
        
        return False
    
    def handle_alias_access(self, field_name: str, context: str) -> bool:
        """Handle SQL alias field access"""
        # Look for SQL alias patterns
        alias_patterns = [
            rf'SELECT.*\s+as\s+{re.escape(field_name)}\b',
            rf'as\s+{re.escape(field_name)}\b',
        ]
        
        for pattern in alias_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return True
        
        return False


class ValidationEngine:
    """Core validation engine with confidence scoring"""
    
    def __init__(self, schema_reader: DatabaseSchemaReader, 
                 context_analyzer: ContextAnalyzer, 
                 pattern_handler: FrappePatternHandler,
                 min_confidence: float = 0.7):
        self.schema_reader = schema_reader
        self.context_analyzer = context_analyzer
        self.pattern_handler = pattern_handler
        self.min_confidence = min_confidence
    
    def validate_file(self, file_path: Path) -> List[ValidationIssue]:
        """Validate all field references in a file"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            return issues
        
        # Get file context
        file_contexts = self.context_analyzer.analyze_file_context(file_path)
        
        # Parse AST for field access
        try:
            tree = ast.parse(content, filename=str(file_path))
            field_accesses = self._extract_field_accesses(tree)
        except SyntaxError:
            # Fallback to regex extraction
            field_accesses = self._extract_field_accesses_regex(content, lines)
        
        # Validate each field access
        for access in field_accesses:
            line_context = file_contexts.get(access['line'], CodeContext(
                variable_assignments={},
                sql_variables=set(),
                child_table_iterations={},
                property_methods=set(),
                frappe_api_calls=set()
            ))
            
            issue = self._validate_field_access(
                access, line_context, lines, str(file_path)
            )
            
            if issue and issue.confidence >= self.min_confidence:
                issues.append(issue)
        
        return issues
    
    def _extract_field_accesses(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract field access patterns from AST"""
        accesses = []
        
        class FieldAccessVisitor(ast.NodeVisitor):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    accesses.append({
                        'obj_name': node.value.id,
                        'field_name': node.attr,
                        'line': node.lineno,
                        'col': node.col_offset
                    })
                self.generic_visit(node)
        
        visitor = FieldAccessVisitor()
        visitor.visit(tree)
        return accesses
    
    def _extract_field_accesses_regex(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Fallback regex-based field access extraction"""
        accesses = []
        
        # Pattern for obj.field access
        pattern = r'\b(\w+)\.(\w+)\b'
        
        for i, line in enumerate(lines):
            for match in re.finditer(pattern, line):
                accesses.append({
                    'obj_name': match.group(1),
                    'field_name': match.group(2),
                    'line': i + 1,
                    'col': match.start()
                })
        
        return accesses
    
    def _validate_field_access(self, access: Dict[str, Any], 
                             line_context: CodeContext, 
                             lines: List[str], 
                             file_path: str) -> Optional[ValidationIssue]:
        """Validate a single field access with confidence scoring"""
        obj_name = access['obj_name']
        field_name = access['field_name']
        line_num = access['line']
        
        # Get line context for analysis
        line_content = lines[line_num - 1] if line_num <= len(lines) else ""
        broader_context = self._get_broader_context(lines, line_num, 5)
        
        # Skip built-in Python and Frappe objects
        if obj_name in self.context_analyzer.builtin_patterns['python_builtins']:
            return None
        
        if obj_name in self.context_analyzer.builtin_patterns['frappe_objects']:
            return None
        
        # Check if this is a valid Frappe pattern
        is_valid_pattern, pattern_type = self.pattern_handler.is_valid_frappe_pattern(
            f"{obj_name}.{field_name}", broader_context
        )
        
        if is_valid_pattern:
            return None
        
        # Determine object type from context
        obj_type = self._determine_object_type(obj_name, line_context, broader_context)
        
        if not obj_type or obj_type == 'unknown':
            # Low confidence - could be legitimate
            return None
        
        # Skip SQL results and other non-DocType objects
        confidence = 1.0
        
        if obj_name in line_context.sql_variables:
            return None
        
        if obj_name in line_context.frappe_api_calls:
            confidence *= 0.3  # Low confidence for API results
        
        if field_name in line_context.property_methods:
            return None
        
        if obj_name in line_context.child_table_iterations:
            obj_type = line_context.child_table_iterations[obj_name]
        
        # Check if field exists in the determined DocType
        if not self.schema_reader.is_valid_field(obj_type, field_name):
            return ValidationIssue(
                file_path=file_path,
                line_number=line_num,
                obj_name=obj_name,
                field_name=field_name,
                doctype=obj_type,
                issue_type="invalid_field",
                message=f"Field '{field_name}' does not exist in DocType '{obj_type}'",
                context=line_content.strip(),
                confidence=confidence,
                suggestion=self._suggest_field_fix(obj_type, field_name)
            )
        
        return None
    
    def _determine_object_type(self, obj_name: str, line_context: CodeContext, 
                             broader_context: str) -> Optional[str]:
        """Determine the DocType of an object"""
        # Check direct assignments first
        if obj_name in line_context.variable_assignments:
            obj_type = line_context.variable_assignments[obj_name]
            if obj_type in self.schema_reader.doctypes:
                return obj_type
        
        # Check child table iterations
        if obj_name in line_context.child_table_iterations:
            return line_context.child_table_iterations[obj_name]
        
        # Try to infer from variable naming conventions
        naming_patterns = {
            'member': 'Member',
            'chapter': 'Chapter', 
            'volunteer': 'Volunteer',
            'contribution': 'Contribution',
            'payment': 'Payment',
            'invoice': 'Sales Invoice',
        }
        
        for pattern, doctype in naming_patterns.items():
            if pattern in obj_name.lower() and doctype in self.schema_reader.doctypes:
                # Lower confidence for naming-based inference
                return doctype
        
        return None
    
    def _suggest_field_fix(self, doctype: str, field_name: str) -> Optional[str]:
        """Suggest a field name fix"""
        if doctype not in self.schema_reader.doctypes:
            return None
        
        schema = self.schema_reader.doctypes[doctype]
        all_fields = list(schema.fields.keys()) + list(schema.custom_fields.keys())
        
        # Simple similarity check
        close_matches = []
        for valid_field in all_fields:
            if self._string_similarity(field_name, valid_field) > 0.7:
                close_matches.append(valid_field)
        
        if close_matches:
            return f"Did you mean: {', '.join(close_matches[:3])}?"
        
        return None
    
    def _string_similarity(self, a: str, b: str) -> float:
        """Simple string similarity calculation"""
        if not a or not b:
            return 0.0
        
        # Simple character-based similarity
        common = set(a.lower()) & set(b.lower())
        total = set(a.lower()) | set(b.lower())
        
        return len(common) / len(total) if total else 0.0
    
    def _get_broader_context(self, lines: List[str], line_num: int, radius: int) -> str:
        """Get broader context around a line"""
        start = max(0, line_num - radius - 1)
        end = min(len(lines), line_num + radius)
        return '\n'.join(lines[start:end])


class SchemaAwareValidator:
    """Main validator class that orchestrates all components"""
    
    def __init__(self, app_path: str, min_confidence: float = 0.7, verbose: bool = False):
        self.app_path = Path(app_path)
        self.min_confidence = min_confidence
        self.verbose = verbose
        
        print("🔍 Initializing Schema-Aware Validator...")
        
        # Initialize components
        self.schema_reader = DatabaseSchemaReader(app_path)
        self.context_analyzer = ContextAnalyzer(self.schema_reader)
        self.pattern_handler = FrappePatternHandler()
        self.validation_engine = ValidationEngine(
            self.schema_reader, 
            self.context_analyzer, 
            self.pattern_handler,
            min_confidence
        )
        
        print("✅ Schema-Aware Validator initialized")
    
    def validate_file(self, file_path: Path) -> List[ValidationIssue]:
        """Validate a single file"""
        if self.verbose:
            print(f"🔍 Validating {file_path}")
        
        return self.validation_engine.validate_file(file_path)
    
    def validate_directory(self, directory: Optional[Path] = None) -> List[ValidationIssue]:
        """Validate all Python files in directory"""
        search_path = directory or self.app_path
        issues = []
        
        print(f"🔍 Validating Python files in {search_path}")
        
        file_count = 0
        for py_file in search_path.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
            
            file_issues = self.validate_file(py_file)
            issues.extend(file_issues)
            file_count += 1
            
            if file_count % 50 == 0:
                print(f"   Processed {file_count} files, found {len(issues)} issues...")
        
        print(f"✅ Validated {file_count} files")
        return issues
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if a file should be skipped"""
        skip_patterns = [
            '__pycache__', '.git', 'node_modules', '.pyc',
            'test_field_validation', 'validator.py', 'validation'
        ]
        
        file_str = str(file_path)
        return any(pattern in file_str for pattern in skip_patterns)
    
    def generate_report(self, issues: List[ValidationIssue]) -> str:
        """Generate comprehensive validation report"""
        if not issues:
            return "✅ No field reference issues found!"
        
        report = []
        report.append(f"🎯 Schema-Aware Validation Results")
        report.append(f"Found {len(issues)} potential field reference issues\n")
        
        # Categorize by confidence
        high_confidence = [i for i in issues if i.confidence >= 0.9]
        medium_confidence = [i for i in issues if 0.7 <= i.confidence < 0.9]
        low_confidence = [i for i in issues if i.confidence < 0.7]
        
        report.append(f"📊 Confidence Distribution:")
        report.append(f"   High confidence (≥90%): {len(high_confidence)} issues")
        report.append(f"   Medium confidence (70-89%): {len(medium_confidence)} issues")
        report.append(f"   Low confidence (<70%): {len(low_confidence)} issues")
        report.append("")
        
        # Show high confidence issues first
        if high_confidence:
            report.append("🚨 High Confidence Issues (likely genuine errors):")
            for issue in high_confidence[:10]:
                report.append(f"❌ {issue.file_path}:{issue.line_number}")
                report.append(f"   {issue.obj_name}.{issue.field_name} (DocType: {issue.doctype})")
                report.append(f"   {issue.message} (confidence: {issue.confidence:.1%})")
                if issue.suggestion:
                    report.append(f"   💡 {issue.suggestion}")
                report.append(f"   Context: {issue.context}")
                report.append("")
        
        # Summary statistics
        by_doctype = defaultdict(int)
        by_file = defaultdict(int)
        
        for issue in issues:
            by_doctype[issue.doctype] += 1
            by_file[issue.file_path] += 1
        
        report.append("📊 Issues by DocType:")
        for doctype, count in sorted(by_doctype.items(), key=lambda x: x[1], reverse=True)[:10]:
            report.append(f"   {doctype}: {count}")
        
        report.append("")
        report.append("📊 Files with most issues:")
        for file_path, count in sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:5]:
            report.append(f"   {file_path}: {count}")
        
        return '\n'.join(report)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Schema-Aware Field Validator')
    parser.add_argument('--app-path', default='/home/frappe/frappe-bench/apps/verenigingen',
                       help='Path to the Frappe app')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='Minimum confidence threshold (0.0-1.0)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--file', type=str,
                       help='Validate single file')
    parser.add_argument('--pre-commit', action='store_true',
                       help='Pre-commit mode (exit with error code if issues found)')
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = SchemaAwareValidator(
        app_path=args.app_path,
        min_confidence=args.min_confidence,
        verbose=args.verbose
    )
    
    # Run validation
    if args.file:
        file_path = Path(args.file)
        issues = validator.validate_file(file_path)
    else:
        issues = validator.validate_directory()
    
    # Generate and print report
    report = validator.generate_report(issues)
    print(report)
    
    # Exit with appropriate code
    if args.pre_commit and issues:
        high_confidence_issues = [i for i in issues if i.confidence >= 0.9]
        if high_confidence_issues:
            print(f"\n❌ Pre-commit validation failed: {len(high_confidence_issues)} high-confidence issues found")
            return 1
    
    print(f"\n✅ Schema-aware validation completed")
    return 0


if __name__ == "__main__":
    exit(main())