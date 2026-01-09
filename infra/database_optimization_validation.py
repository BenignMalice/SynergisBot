"""
Database Performance Optimization Validation System

This module implements a comprehensive validation system to ensure database
performance is optimized for production use, including query optimization,
index efficiency, connection pooling, and overall database health.

Key Features:
- Database performance optimization validation
- Query optimization analysis and recommendations
- Index efficiency assessment and optimization
- Connection pooling performance validation
- Database health monitoring and analysis
- Automated optimization recommendations
- Performance bottleneck identification
- Database load testing and validation
"""

import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import hashlib
import logging
import sqlite3
import psutil
import os
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import tempfile
import shutil

logger = logging.getLogger(__name__)

class DatabaseOptimizationLevel(Enum):
    """Database optimization level"""
    EXCELLENT = "excellent"  # >95% optimization
    GOOD = "good"  # 80-95% optimization
    FAIR = "fair"  # 60-80% optimization
    POOR = "poor"  # 40-60% optimization
    CRITICAL = "critical"  # <40% optimization

class OptimizationStatus(Enum):
    """Optimization status"""
    OPTIMIZED = "optimized"  # Fully optimized
    PARTIALLY_OPTIMIZED = "partially_optimized"  # Some optimizations applied
    NEEDS_OPTIMIZATION = "needs_optimization"  # Requires optimization
    CRITICAL_OPTIMIZATION = "critical_optimization"  # Critical optimization needed

class QueryType(Enum):
    """Query type classification"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    DROP = "drop"
    ALTER = "alter"
    INDEX = "index"
    VACUUM = "vacuum"
    ANALYZE = "analyze"

class IndexType(Enum):
    """Index type classification"""
    PRIMARY_KEY = "primary_key"
    UNIQUE = "unique"
    COMPOSITE = "composite"
    SINGLE_COLUMN = "single_column"
    COVERING = "covering"
    PARTIAL = "partial"

@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_id: str
    query_type: QueryType
    execution_time_ms: float
    rows_affected: int
    index_usage: bool
    full_table_scan: bool
    temporary_table: bool
    sort_operation: bool
    join_operations: int
    subquery_count: int
    complexity_score: float
    optimization_score: float
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IndexMetrics:
    """Index performance metrics"""
    index_name: str
    table_name: str
    index_type: IndexType
    column_count: int
    size_bytes: int
    usage_count: int
    efficiency_score: float
    selectivity: float
    fragmentation_level: float
    maintenance_cost: float
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConnectionPoolMetrics:
    """Connection pool performance metrics"""
    total_connections: int
    active_connections: int
    idle_connections: int
    connection_wait_time_ms: float
    connection_utilization: float
    pool_efficiency: float
    timeout_events: int
    connection_errors: int
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatabaseOptimizationValidation:
    """Database optimization validation result"""
    timestamp: float
    database_name: str
    optimization_level: DatabaseOptimizationLevel
    optimization_status: OptimizationStatus
    overall_score: float
    query_optimization_score: float
    index_optimization_score: float
    connection_pool_score: float
    database_health_score: float
    performance_improvement: float
    bottlenecks_identified: List[str]
    optimization_recommendations: List[str]
    critical_issues: List[str]
    query_metrics: List[QueryMetrics]
    index_metrics: List[IndexMetrics]
    connection_pool_metrics: ConnectionPoolMetrics
    detailed_analysis: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatabaseOptimizationReport:
    """Database optimization report"""
    timestamp: float
    database_name: str
    overall_optimization_score: float
    optimization_level: DatabaseOptimizationLevel
    total_queries_analyzed: int
    total_indexes_analyzed: int
    optimization_opportunities: int
    performance_gains_estimated: float
    critical_optimizations_needed: int
    recommendations: List[str]
    detailed_validations: List[DatabaseOptimizationValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class DatabaseOptimizationValidator:
    """Database optimization validator for comprehensive performance validation"""
    
    def __init__(self, database_path: str = None):
        self.database_path = database_path
        self.query_history: List[QueryMetrics] = []
        self.index_metrics: List[IndexMetrics] = []
        self.connection_pool_metrics: Optional[ConnectionPoolMetrics] = None
        self.lock = threading.RLock()
        self.start_time = time.time()
        
        # Performance thresholds
        self.query_time_threshold_ms = 50.0
        self.index_efficiency_threshold = 0.8
        self.connection_utilization_threshold = 0.7
        self.optimization_score_threshold = 0.8
    
    def analyze_query_performance(self, query: str, execution_time_ms: float, 
                                rows_affected: int = 0) -> QueryMetrics:
        """Analyze query performance and generate metrics"""
        query_id = hashlib.md5(query.encode()).hexdigest()[:8]
        query_type = self._classify_query_type(query)
        
        # Analyze query characteristics
        index_usage = self._check_index_usage(query)
        full_table_scan = self._check_full_table_scan(query)
        temporary_table = self._check_temporary_table(query)
        sort_operation = self._check_sort_operation(query)
        join_operations = self._count_join_operations(query)
        subquery_count = self._count_subqueries(query)
        
        # Calculate complexity and optimization scores
        complexity_score = self._calculate_query_complexity(
            join_operations, subquery_count, sort_operation, temporary_table
        )
        optimization_score = self._calculate_query_optimization_score(
            execution_time_ms, index_usage, full_table_scan, complexity_score
        )
        
        # Generate recommendations
        recommendations = self._generate_query_recommendations(
            query, execution_time_ms, index_usage, full_table_scan, 
            complexity_score, optimization_score
        )
        
        metrics = QueryMetrics(
            query_id=query_id,
            query_type=query_type,
            execution_time_ms=execution_time_ms,
            rows_affected=rows_affected,
            index_usage=index_usage,
            full_table_scan=full_table_scan,
            temporary_table=temporary_table,
            sort_operation=sort_operation,
            join_operations=join_operations,
            subquery_count=subquery_count,
            complexity_score=complexity_score,
            optimization_score=optimization_score,
            recommendations=recommendations,
            metadata={
                "query_preview": query[:100] + "..." if len(query) > 100 else query,
                "analysis_timestamp": time.time()
            }
        )
        
        with self.lock:
            self.query_history.append(metrics)
        
        return metrics
    
    def analyze_index_efficiency(self, index_name: str, table_name: str, 
                               index_type: IndexType, column_count: int,
                               size_bytes: int, usage_count: int) -> IndexMetrics:
        """Analyze index efficiency and generate metrics"""
        # Calculate efficiency metrics
        efficiency_score = self._calculate_index_efficiency(
            usage_count, size_bytes, column_count
        )
        selectivity = self._calculate_index_selectivity(usage_count, size_bytes)
        fragmentation_level = self._calculate_fragmentation_level(size_bytes, usage_count)
        maintenance_cost = self._calculate_maintenance_cost(size_bytes, column_count)
        
        # Generate recommendations
        recommendations = self._generate_index_recommendations(
            index_name, efficiency_score, selectivity, fragmentation_level,
            maintenance_cost, index_type
        )
        
        metrics = IndexMetrics(
            index_name=index_name,
            table_name=table_name,
            index_type=index_type,
            column_count=column_count,
            size_bytes=size_bytes,
            usage_count=usage_count,
            efficiency_score=efficiency_score,
            selectivity=selectivity,
            fragmentation_level=fragmentation_level,
            maintenance_cost=maintenance_cost,
            recommendations=recommendations,
            metadata={
                "analysis_timestamp": time.time(),
                "table_name": table_name
            }
        )
        
        with self.lock:
            self.index_metrics.append(metrics)
        
        return metrics
    
    def analyze_connection_pool(self, total_connections: int, active_connections: int,
                              idle_connections: int, connection_wait_time_ms: float,
                              timeout_events: int = 0, connection_errors: int = 0) -> ConnectionPoolMetrics:
        """Analyze connection pool performance"""
        connection_utilization = active_connections / total_connections if total_connections > 0 else 0.0
        pool_efficiency = self._calculate_pool_efficiency(
            active_connections, idle_connections, connection_wait_time_ms
        )
        
        # Generate recommendations
        recommendations = self._generate_connection_pool_recommendations(
            connection_utilization, pool_efficiency, timeout_events, connection_errors
        )
        
        metrics = ConnectionPoolMetrics(
            total_connections=total_connections,
            active_connections=active_connections,
            idle_connections=idle_connections,
            connection_wait_time_ms=connection_wait_time_ms,
            connection_utilization=connection_utilization,
            pool_efficiency=pool_efficiency,
            timeout_events=timeout_events,
            connection_errors=connection_errors,
            recommendations=recommendations,
            metadata={
                "analysis_timestamp": time.time()
            }
        )
        
        with self.lock:
            self.connection_pool_metrics = metrics
        
        return metrics
    
    def validate_database_optimization(self, database_name: str = "main") -> DatabaseOptimizationValidation:
        """Validate overall database optimization"""
        with self.lock:
            # Calculate optimization scores
            query_optimization_score = self._calculate_query_optimization_score_overall()
            index_optimization_score = self._calculate_index_optimization_score_overall()
            connection_pool_score = self._calculate_connection_pool_score()
            database_health_score = self._calculate_database_health_score()
            
            # Calculate overall optimization score
            overall_score = (
                query_optimization_score * 0.4 +
                index_optimization_score * 0.3 +
                connection_pool_score * 0.2 +
                database_health_score * 0.1
            )
            
            # Determine optimization level and status
            optimization_level = self._determine_optimization_level(overall_score)
            optimization_status = self._determine_optimization_status(overall_score)
            
            # Calculate performance improvement
            performance_improvement = self._calculate_performance_improvement()
            
            # Identify bottlenecks and critical issues
            bottlenecks_identified = self._identify_bottlenecks()
            critical_issues = self._identify_critical_issues()
            
            # Generate optimization recommendations
            optimization_recommendations = self._generate_optimization_recommendations(
                query_optimization_score, index_optimization_score, 
                connection_pool_score, database_health_score
            )
            
            # Detailed analysis
            detailed_analysis = self._generate_detailed_analysis()
            
            validation = DatabaseOptimizationValidation(
                timestamp=time.time(),
                database_name=database_name,
                optimization_level=optimization_level,
                optimization_status=optimization_status,
                overall_score=overall_score,
                query_optimization_score=query_optimization_score,
                index_optimization_score=index_optimization_score,
                connection_pool_score=connection_pool_score,
                database_health_score=database_health_score,
                performance_improvement=performance_improvement,
                bottlenecks_identified=bottlenecks_identified,
                optimization_recommendations=optimization_recommendations,
                critical_issues=critical_issues,
                query_metrics=self.query_history.copy(),
                index_metrics=self.index_metrics.copy(),
                connection_pool_metrics=self.connection_pool_metrics or ConnectionPoolMetrics(
                    total_connections=0, active_connections=0, idle_connections=0,
                    connection_wait_time_ms=0.0, connection_utilization=0.0,
                    pool_efficiency=0.0, timeout_events=0, connection_errors=0
                ),
                detailed_analysis=detailed_analysis,
                metadata={
                    "validation_duration": time.time() - self.start_time,
                    "total_queries": len(self.query_history),
                    "total_indexes": len(self.index_metrics)
                }
            )
        
        return validation
    
    def generate_optimization_report(self, database_name: str = "main") -> DatabaseOptimizationReport:
        """Generate comprehensive database optimization report"""
        validation = self.validate_database_optimization(database_name)
        
        # Calculate report metrics
        total_queries_analyzed = len(self.query_history)
        total_indexes_analyzed = len(self.index_metrics)
        optimization_opportunities = len([
            q for q in self.query_history if q.optimization_score < 0.8
        ]) + len([
            i for i in self.index_metrics if i.efficiency_score < 0.8
        ])
        
        performance_gains_estimated = self._estimate_performance_gains()
        critical_optimizations_needed = len(validation.critical_issues)
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(validation)
        
        return DatabaseOptimizationReport(
            timestamp=time.time(),
            database_name=database_name,
            overall_optimization_score=validation.overall_score,
            optimization_level=validation.optimization_level,
            total_queries_analyzed=total_queries_analyzed,
            total_indexes_analyzed=total_indexes_analyzed,
            optimization_opportunities=optimization_opportunities,
            performance_gains_estimated=performance_gains_estimated,
            critical_optimizations_needed=critical_optimizations_needed,
            recommendations=recommendations,
            detailed_validations=[validation],
            metadata={
                "report_generation_time": time.time(),
                "analysis_duration": time.time() - self.start_time
            }
        )
    
    def _classify_query_type(self, query: str) -> QueryType:
        """Classify query type"""
        query_lower = query.lower().strip()
        if query_lower.startswith('select'):
            return QueryType.SELECT
        elif query_lower.startswith('insert'):
            return QueryType.INSERT
        elif query_lower.startswith('update'):
            return QueryType.UPDATE
        elif query_lower.startswith('delete'):
            return QueryType.DELETE
        elif query_lower.startswith('create'):
            return QueryType.CREATE
        elif query_lower.startswith('drop'):
            return QueryType.DROP
        elif query_lower.startswith('alter'):
            return QueryType.ALTER
        elif 'index' in query_lower:
            return QueryType.INDEX
        elif query_lower.startswith('vacuum'):
            return QueryType.VACUUM
        elif query_lower.startswith('analyze'):
            return QueryType.ANALYZE
        else:
            return QueryType.SELECT
    
    def _check_index_usage(self, query: str) -> bool:
        """Check if query uses indexes effectively"""
        query_lower = query.lower()
        # Simple heuristics for index usage
        has_where = 'where' in query_lower
        has_order_by = 'order by' in query_lower
        has_join = 'join' in query_lower
        
        return has_where or has_order_by or has_join
    
    def _check_full_table_scan(self, query: str) -> bool:
        """Check if query might cause full table scan"""
        query_lower = query.lower()
        # Simple heuristics for full table scan detection
        no_where = 'where' not in query_lower
        no_index_hints = 'use index' not in query_lower and 'force index' not in query_lower
        has_like_wildcard = '%' in query_lower and 'like' in query_lower
        
        return (no_where and no_index_hints) or has_like_wildcard
    
    def _check_temporary_table(self, query: str) -> bool:
        """Check if query uses temporary tables"""
        query_lower = query.lower()
        return 'temp' in query_lower or 'temporary' in query_lower
    
    def _check_sort_operation(self, query: str) -> bool:
        """Check if query has sort operations"""
        query_lower = query.lower()
        return 'order by' in query_lower or 'group by' in query_lower
    
    def _count_join_operations(self, query: str) -> int:
        """Count join operations in query"""
        query_lower = query.lower()
        return query_lower.count('join')
    
    def _count_subqueries(self, query: str) -> int:
        """Count subqueries in query"""
        query_lower = query.lower()
        return query_lower.count('(select') - query_lower.count('(select select')
    
    def _calculate_query_complexity(self, join_operations: int, subquery_count: int,
                                   sort_operation: bool, temporary_table: bool) -> float:
        """Calculate query complexity score"""
        complexity = 0.0
        complexity += join_operations * 0.2
        complexity += subquery_count * 0.3
        complexity += 0.1 if sort_operation else 0.0
        complexity += 0.2 if temporary_table else 0.0
        
        return min(complexity, 1.0)
    
    def _calculate_query_optimization_score(self, execution_time_ms: float, index_usage: bool,
                                          full_table_scan: bool, complexity_score: float) -> float:
        """Calculate query optimization score"""
        score = 1.0
        
        # Time penalty
        if execution_time_ms > self.query_time_threshold_ms:
            score -= 0.3
        
        # Index usage bonus
        if index_usage:
            score += 0.2
        
        # Full table scan penalty
        if full_table_scan:
            score -= 0.4
        
        # Complexity penalty
        score -= complexity_score * 0.2
        
        return min(max(score, 0.0), 1.0)  # Ensure score is between 0.0 and 1.0
    
    def _calculate_index_efficiency(self, usage_count: int, size_bytes: int, column_count: int) -> float:
        """Calculate index efficiency score"""
        if usage_count == 0:
            return 0.0
        
        # Efficiency based on usage vs size
        usage_density = usage_count / (size_bytes / 1024) if size_bytes > 0 else 0.0
        column_efficiency = 1.0 / column_count if column_count > 0 else 1.0
        
        return min(usage_density * column_efficiency, 1.0)
    
    def _calculate_index_selectivity(self, usage_count: int, size_bytes: int) -> float:
        """Calculate index selectivity"""
        if usage_count == 0 or size_bytes == 0:
            return 0.0
        
        # Higher selectivity is better (more unique values)
        return min(usage_count / (size_bytes / 1024), 1.0)
    
    def _calculate_fragmentation_level(self, size_bytes: int, usage_count: int) -> float:
        """Calculate index fragmentation level"""
        if usage_count == 0:
            return 1.0  # High fragmentation if unused
        
        # Simple fragmentation estimation
        return min(size_bytes / (usage_count * 1024), 1.0)
    
    def _calculate_maintenance_cost(self, size_bytes: int, column_count: int) -> float:
        """Calculate index maintenance cost"""
        size_cost = size_bytes / (1024 * 1024)  # MB
        column_cost = column_count * 0.1
        
        return min(size_cost + column_cost, 1.0)
    
    def _calculate_pool_efficiency(self, active_connections: int, idle_connections: int,
                                  connection_wait_time_ms: float) -> float:
        """Calculate connection pool efficiency"""
        if active_connections + idle_connections == 0:
            return 0.0
        
        utilization = active_connections / (active_connections + idle_connections)
        wait_penalty = min(connection_wait_time_ms / 1000, 1.0)  # Penalty for wait time
        
        return max(utilization - wait_penalty, 0.0)
    
    def _calculate_query_optimization_score_overall(self) -> float:
        """Calculate overall query optimization score"""
        if not self.query_history:
            return 0.0
        
        scores = [q.optimization_score for q in self.query_history]
        return statistics.mean(scores)
    
    def _calculate_index_optimization_score_overall(self) -> float:
        """Calculate overall index optimization score"""
        if not self.index_metrics:
            return 0.0
        
        scores = [i.efficiency_score for i in self.index_metrics]
        return statistics.mean(scores)
    
    def _calculate_connection_pool_score(self) -> float:
        """Calculate connection pool score"""
        if not self.connection_pool_metrics:
            return 0.0
        
        return self.connection_pool_metrics.pool_efficiency
    
    def _calculate_database_health_score(self) -> float:
        """Calculate database health score"""
        # Simple health score based on available metrics
        health_score = 1.0
        
        # Penalty for slow queries
        slow_queries = len([q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms])
        if self.query_history:
            health_score -= (slow_queries / len(self.query_history)) * 0.5
        
        # Penalty for inefficient indexes
        inefficient_indexes = len([i for i in self.index_metrics if i.efficiency_score < self.index_efficiency_threshold])
        if self.index_metrics:
            health_score -= (inefficient_indexes / len(self.index_metrics)) * 0.3
        
        return max(health_score, 0.0)
    
    def _determine_optimization_level(self, overall_score: float) -> DatabaseOptimizationLevel:
        """Determine optimization level"""
        if overall_score >= 0.95:
            return DatabaseOptimizationLevel.EXCELLENT
        elif overall_score >= 0.8:
            return DatabaseOptimizationLevel.GOOD
        elif overall_score >= 0.6:
            return DatabaseOptimizationLevel.FAIR
        elif overall_score >= 0.4:
            return DatabaseOptimizationLevel.POOR
        else:
            return DatabaseOptimizationLevel.CRITICAL
    
    def _determine_optimization_status(self, overall_score: float) -> OptimizationStatus:
        """Determine optimization status"""
        if overall_score >= 0.9:
            return OptimizationStatus.OPTIMIZED
        elif overall_score >= 0.7:
            return OptimizationStatus.PARTIALLY_OPTIMIZED
        elif overall_score >= 0.5:
            return OptimizationStatus.NEEDS_OPTIMIZATION
        else:
            return OptimizationStatus.CRITICAL_OPTIMIZATION
    
    def _calculate_performance_improvement(self) -> float:
        """Calculate estimated performance improvement"""
        if not self.query_history:
            return 0.0
        
        # Estimate improvement based on optimization opportunities
        slow_queries = [q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms]
        if not slow_queries:
            return 0.0
        
        current_avg_time = statistics.mean([q.execution_time_ms for q in slow_queries])
        optimized_avg_time = current_avg_time * 0.5  # Assume 50% improvement
        
        return (current_avg_time - optimized_avg_time) / current_avg_time
    
    def _identify_bottlenecks(self) -> List[str]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Query bottlenecks
        slow_queries = [q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms]
        if slow_queries:
            bottlenecks.append(f"{len(slow_queries)} slow queries detected")
        
        # Index bottlenecks
        inefficient_indexes = [i for i in self.index_metrics if i.efficiency_score < self.index_efficiency_threshold]
        if inefficient_indexes:
            bottlenecks.append(f"{len(inefficient_indexes)} inefficient indexes detected")
        
        # Connection pool bottlenecks
        if self.connection_pool_metrics and self.connection_pool_metrics.connection_utilization > self.connection_utilization_threshold:
            bottlenecks.append("High connection pool utilization")
        
        return bottlenecks
    
    def _identify_critical_issues(self) -> List[str]:
        """Identify critical optimization issues"""
        issues = []
        
        # Critical query issues
        very_slow_queries = [q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms * 2]
        if very_slow_queries:
            issues.append(f"{len(very_slow_queries)} very slow queries (>100ms)")
        
        # Critical index issues
        very_inefficient_indexes = [i for i in self.index_metrics if i.efficiency_score < 0.3]
        if very_inefficient_indexes:
            issues.append(f"{len(very_inefficient_indexes)} very inefficient indexes")
        
        # Critical connection issues
        if self.connection_pool_metrics and self.connection_pool_metrics.connection_errors > 0:
            issues.append(f"{self.connection_pool_metrics.connection_errors} connection errors")
        
        return issues
    
    def _generate_query_recommendations(self, query: str, execution_time_ms: float,
                                      index_usage: bool, full_table_scan: bool,
                                      complexity_score: float, optimization_score: float) -> List[str]:
        """Generate query-specific recommendations"""
        recommendations = []
        
        if execution_time_ms > self.query_time_threshold_ms:
            recommendations.append("Query execution time exceeds threshold - consider optimization")
        
        if not index_usage:
            recommendations.append("Add appropriate indexes to improve query performance")
        
        if full_table_scan:
            recommendations.append("Avoid full table scans - add WHERE clauses or indexes")
        
        if complexity_score > 0.7:
            recommendations.append("Query complexity is high - consider breaking into smaller queries")
        
        if optimization_score < 0.5:
            recommendations.append("Query needs significant optimization")
        
        return recommendations
    
    def _generate_index_recommendations(self, index_name: str, efficiency_score: float,
                                      selectivity: float, fragmentation_level: float,
                                      maintenance_cost: float, index_type: IndexType) -> List[str]:
        """Generate index-specific recommendations"""
        recommendations = []
        
        if efficiency_score < self.index_efficiency_threshold:
            recommendations.append(f"Index {index_name} has low efficiency - consider optimization")
        
        if selectivity < 0.5:
            recommendations.append(f"Index {index_name} has low selectivity - consider dropping or redesigning")
        
        if fragmentation_level > 0.7:
            recommendations.append(f"Index {index_name} is highly fragmented - consider rebuilding")
        
        if maintenance_cost > 0.8:
            recommendations.append(f"Index {index_name} has high maintenance cost - consider if necessary")
        
        return recommendations
    
    def _generate_connection_pool_recommendations(self, connection_utilization: float,
                                                pool_efficiency: float, timeout_events: int,
                                                connection_errors: int) -> List[str]:
        """Generate connection pool recommendations"""
        recommendations = []
        
        if connection_utilization > self.connection_utilization_threshold:
            recommendations.append("High connection utilization - consider increasing pool size")
        
        if pool_efficiency < 0.5:
            recommendations.append("Low pool efficiency - review connection management")
        
        if timeout_events > 0:
            recommendations.append(f"{timeout_events} connection timeouts - check pool configuration")
        
        if connection_errors > 0:
            recommendations.append(f"{connection_errors} connection errors - investigate network/database issues")
        
        return recommendations
    
    def _generate_optimization_recommendations(self, query_score: float, index_score: float,
                                             connection_score: float, health_score: float) -> List[str]:
        """Generate overall optimization recommendations"""
        recommendations = []
        
        if query_score < 0.8:
            recommendations.append("Focus on query optimization - analyze slow queries")
        
        if index_score < 0.8:
            recommendations.append("Optimize indexes - review index usage and efficiency")
        
        if connection_score < 0.8:
            recommendations.append("Optimize connection pool - review pool configuration")
        
        if health_score < 0.8:
            recommendations.append("Improve database health - address performance issues")
        
        return recommendations
    
    def _generate_detailed_analysis(self) -> Dict[str, Any]:
        """Generate detailed analysis"""
        return {
            "query_analysis": {
                "total_queries": len(self.query_history),
                "slow_queries": len([q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms]),
                "avg_execution_time": statistics.mean([q.execution_time_ms for q in self.query_history]) if self.query_history else 0.0,
                "complexity_distribution": self._analyze_complexity_distribution()
            },
            "index_analysis": {
                "total_indexes": len(self.index_metrics),
                "inefficient_indexes": len([i for i in self.index_metrics if i.efficiency_score < self.index_efficiency_threshold]),
                "avg_efficiency": statistics.mean([i.efficiency_score for i in self.index_metrics]) if self.index_metrics else 0.0,
                "size_distribution": self._analyze_index_size_distribution()
            },
            "connection_analysis": {
                "pool_metrics": self.connection_pool_metrics.__dict__ if self.connection_pool_metrics else {},
                "efficiency": self.connection_pool_metrics.pool_efficiency if self.connection_pool_metrics else 0.0
            }
        }
    
    def _analyze_complexity_distribution(self) -> Dict[str, int]:
        """Analyze query complexity distribution"""
        if not self.query_history:
            return {}
        
        low_complexity = len([q for q in self.query_history if q.complexity_score < 0.3])
        medium_complexity = len([q for q in self.query_history if 0.3 <= q.complexity_score < 0.7])
        high_complexity = len([q for q in self.query_history if q.complexity_score >= 0.7])
        
        return {
            "low": low_complexity,
            "medium": medium_complexity,
            "high": high_complexity
        }
    
    def _analyze_index_size_distribution(self) -> Dict[str, int]:
        """Analyze index size distribution"""
        if not self.index_metrics:
            return {}
        
        small_indexes = len([i for i in self.index_metrics if i.size_bytes < 1024 * 1024])  # <1MB
        medium_indexes = len([i for i in self.index_metrics if 1024 * 1024 <= i.size_bytes < 10 * 1024 * 1024])  # 1-10MB
        large_indexes = len([i for i in self.index_metrics if i.size_bytes >= 10 * 1024 * 1024])  # >=10MB
        
        return {
            "small": small_indexes,
            "medium": medium_indexes,
            "large": large_indexes
        }
    
    def _estimate_performance_gains(self) -> float:
        """Estimate potential performance gains"""
        if not self.query_history:
            return 0.0
        
        # Estimate gains from query optimization
        slow_queries = [q for q in self.query_history if q.execution_time_ms > self.query_time_threshold_ms]
        if not slow_queries:
            return 0.0
        
        current_total_time = sum(q.execution_time_ms for q in slow_queries)
        optimized_total_time = current_total_time * 0.5  # Assume 50% improvement
        
        return (current_total_time - optimized_total_time) / current_total_time
    
    def _generate_report_recommendations(self, validation: DatabaseOptimizationValidation) -> List[str]:
        """Generate report-level recommendations"""
        recommendations = []
        
        if validation.optimization_level == DatabaseOptimizationLevel.CRITICAL:
            recommendations.append("CRITICAL: Database requires immediate optimization")
        elif validation.optimization_level == DatabaseOptimizationLevel.POOR:
            recommendations.append("Database performance is poor - optimization needed")
        elif validation.optimization_level == DatabaseOptimizationLevel.FAIR:
            recommendations.append("Database performance is fair - consider optimizations")
        elif validation.optimization_level == DatabaseOptimizationLevel.GOOD:
            recommendations.append("Database performance is good - minor optimizations may help")
        else:
            recommendations.append("Database performance is excellent")
        
        if validation.critical_issues:
            recommendations.append(f"Address {len(validation.critical_issues)} critical issues")
        
        if validation.bottlenecks_identified:
            recommendations.append(f"Resolve {len(validation.bottlenecks_identified)} performance bottlenecks")
        
        return recommendations
    
    def validate_optimization(self, database_name: str = "main") -> DatabaseOptimizationValidation:
        """Validate database optimization - alias for backward compatibility"""
        return self.validate_database_optimization(database_name)

# Global database optimization validator
_database_optimization_validator: Optional[DatabaseOptimizationValidator] = None

def get_database_optimization_validator(database_path: str = None) -> DatabaseOptimizationValidator:
    """Get global database optimization validator instance"""
    global _database_optimization_validator
    if _database_optimization_validator is None:
        _database_optimization_validator = DatabaseOptimizationValidator(database_path)
    return _database_optimization_validator

def analyze_query_performance(query: str, execution_time_ms: float, rows_affected: int = 0) -> QueryMetrics:
    """Analyze query performance"""
    validator = get_database_optimization_validator()
    return validator.analyze_query_performance(query, execution_time_ms, rows_affected)

def analyze_index_efficiency(index_name: str, table_name: str, index_type: IndexType,
                           column_count: int, size_bytes: int, usage_count: int) -> IndexMetrics:
    """Analyze index efficiency"""
    validator = get_database_optimization_validator()
    return validator.analyze_index_efficiency(index_name, table_name, index_type, column_count, size_bytes, usage_count)

def analyze_connection_pool(total_connections: int, active_connections: int, idle_connections: int,
                          connection_wait_time_ms: float, timeout_events: int = 0, connection_errors: int = 0) -> ConnectionPoolMetrics:
    """Analyze connection pool performance"""
    validator = get_database_optimization_validator()
    return validator.analyze_connection_pool(total_connections, active_connections, idle_connections,
                                            connection_wait_time_ms, timeout_events, connection_errors)

def validate_database_optimization(database_name: str = "main") -> DatabaseOptimizationValidation:
    """Validate database optimization"""
    validator = get_database_optimization_validator()
    return validator.validate_database_optimization(database_name)

def generate_optimization_report(database_name: str = "main") -> DatabaseOptimizationReport:
    """Generate database optimization report"""
    validator = get_database_optimization_validator()
    return validator.generate_optimization_report(database_name)

if __name__ == "__main__":
    # Example usage
    validator = get_database_optimization_validator()
    
    # Analyze some example queries
    queries = [
        ("SELECT * FROM trades WHERE symbol = 'BTCUSDc'", 25.0, 100),
        ("SELECT * FROM trades WHERE timestamp > '2024-01-01'", 150.0, 1000),
        ("SELECT COUNT(*) FROM trades", 5.0, 1),
        ("INSERT INTO trades (symbol, price) VALUES ('EURUSDc', 1.1000)", 10.0, 1)
    ]
    
    for query, time_ms, rows in queries:
        analyze_query_performance(query, time_ms, rows)
    
    # Analyze some example indexes
    indexes = [
        ("idx_trades_symbol", "trades", IndexType.SINGLE_COLUMN, 1, 1024 * 1024, 1000),
        ("idx_trades_timestamp", "trades", IndexType.SINGLE_COLUMN, 1, 2 * 1024 * 1024, 500),
        ("idx_trades_composite", "trades", IndexType.COMPOSITE, 3, 5 * 1024 * 1024, 200)
    ]
    
    for index_name, table_name, index_type, column_count, size_bytes, usage_count in indexes:
        analyze_index_efficiency(index_name, table_name, index_type, column_count, size_bytes, usage_count)
    
    # Analyze connection pool
    analyze_connection_pool(10, 7, 3, 50.0, 0, 0)
    
    # Generate optimization report
    report = generate_optimization_report("trading_db")
    
    print(f"Database Optimization Report:")
    print(f"Overall Score: {report.overall_optimization_score:.2%}")
    print(f"Optimization Level: {report.optimization_level.value}")
    print(f"Queries Analyzed: {report.total_queries_analyzed}")
    print(f"Indexes Analyzed: {report.total_indexes_analyzed}")
    print(f"Optimization Opportunities: {report.optimization_opportunities}")
    print(f"Performance Gains Estimated: {report.performance_gains_estimated:.2%}")
    print(f"Critical Optimizations Needed: {report.critical_optimizations_needed}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
