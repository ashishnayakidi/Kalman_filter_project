# Data Size Strategy for Development

## Executive Summary

**Recommendation: Use 5-10 vehicles (~2-4M rows) for development and testing**

This provides:
- ✅ Fast iteration (5-30 minutes processing time)
- ✅ Sufficient data for meaningful EKF results
- ✅ Multiple cycles per vehicle for trend analysis
- ✅ Manageable storage (~50-100 MB)
- ✅ Easy to scale up later

---

## Is Using Small Data a Good Approach?

### ✅ **YES - For Development/Testing**

**Advantages:**
1. **Fast Iteration**: Test changes in minutes, not hours
2. **Quick Debugging**: Easier to identify issues
3. **Lower Resource Usage**: Less memory, storage, CPU
4. **Development Speed**: Can test multiple scenarios quickly
5. **Cost Effective**: Less compute time during development

**Disadvantages:**
1. **Limited Statistical Power**: May miss edge cases
2. **Less Realistic**: Production will have more data
3. **May Miss Patterns**: Some patterns only appear at scale

### ✅ **But Scale Up for Production**

- Use full dataset (or larger subset) for:
  - Final validation
  - Production deployment
  - Performance benchmarking
  - Statistical analysis

---

## Recommended Data Sizes

### **Tier 1: Quick Testing (1-2 vehicles)**
- **Size**: ~370k-740k rows
- **Storage**: ~12-24 MB
- **Processing Time**: 6-12 minutes
- **Use Case**: 
  - Quick EKF validation
  - Testing code changes
  - Debugging issues
  - Unit testing

### **Tier 2: Development/Testing (5-10 vehicles)** ⭐ **RECOMMENDED**
- **Size**: ~1.9M-3.7M rows
- **Storage**: ~58-116 MB
- **Processing Time**: 30-60 minutes
- **Use Case**:
  - Full pipeline testing
  - EKF parameter tuning
  - Daily summaries validation
  - API endpoint testing
  - **This is the sweet spot for development**

### **Tier 3: Validation (20-50 vehicles)**
- **Size**: ~7.4M-18.5M rows
- **Storage**: ~230-580 MB
- **Processing Time**: 2-5 hours
- **Use Case**:
  - Pre-production validation
  - Performance testing
  - Statistical validation
  - Trend analysis

### **Tier 4: Production (Full Dataset)**
- **Size**: 80.5M rows (all 217 vehicles)
- **Storage**: 2.45 GB
- **Processing Time**: 4-8 hours
- **Use Case**:
  - Production deployment
  - Final validation
  - Complete analysis

---

## Data Size Analysis

### Current Dataset Structure
- **Total**: 80,527,488 rows
- **Vehicles**: 217
- **Avg rows per vehicle**: ~371,094 rows
- **Cycles per vehicle**: 1-1,352 cycles (varies)

### Vehicle Distribution
- **Smallest**: ~100k rows (few cycles)
- **Largest**: ~1.4M rows (1,077 cycles)
- **Median**: ~370k rows

### What Constitutes "Meaningful" Data?

**Minimum for EKF:**
- **1 cycle**: ~128 rows (too small, not meaningful)
- **10 cycles**: ~1,280 rows (basic validation)
- **50 cycles**: ~6,400 rows (good for single vehicle)
- **100+ cycles**: ~12,800+ rows (excellent for trends)

**For Multiple Vehicles:**
- **1 vehicle**: Can test EKF, but no diversity
- **5 vehicles**: Good diversity, multiple patterns
- **10 vehicles**: Excellent for development
- **20+ vehicles**: Production-like diversity

---

## Recommended Strategy

### **Phase 1: Development (Now)**
**Use: 5-10 vehicles (~2-4M rows)**

**Why:**
- Fast enough for iteration (30-60 min)
- Large enough for meaningful results
- Multiple vehicles = diversity
- Multiple cycles = trend analysis
- Manageable storage (~100 MB)

**Selection Strategy:**
- Pick diverse vehicles (different cycle counts)
- Include vehicles with varying patterns
- Ensure good coverage of data ranges

### **Phase 2: Validation (Before Production)**
**Use: 20-50 vehicles (~7-19M rows)**

**Why:**
- More statistical power
- Better validation of trends
- Performance testing
- Edge case detection

### **Phase 3: Production**
**Use: Full dataset (all 217 vehicles)**

**Why:**
- Complete coverage
- Maximum statistical power
- Production-ready scale

---

## Implementation Plan

### **Option A: Create Subset Parquet Files** ⭐ **RECOMMENDED**

Create a subset of the Parquet data for development:

```python
# Select 10 diverse vehicles
selected_vehicles = [0, 1, 2, 25, 51, 56, 69, 91, 140, 216]

# Copy their Parquet partitions to data/parquet_dev/
# This gives you ~3.7M rows for development
```

**Benefits:**
- Keep full dataset intact
- Easy to switch between dev/prod
- Fast queries (smaller dataset)
- Can scale up by adding more vehicles

### **Option B: Use Row Limits**

Process only first N rows or first N vehicles:

```python
# Process only first 10 vehicles
vehicles_to_process = vehicles[:10]
```

**Benefits:**
- Simple to implement
- No need to create separate files

**Drawbacks:**
- May not be diverse
- Need to modify code each time

### **Option C: Sampling**

Random sample of rows across all vehicles:

```python
# Sample 10% of rows from all vehicles
sample_rate = 0.10
```

**Benefits:**
- Maintains diversity
- Representative sample

**Drawbacks:**
- May break vehicle-level analysis
- Harder to maintain relationships

---

## Storage & Performance Comparison

| Data Size | Rows | Storage | EKF Time | Use Case |
|-----------|------|---------|----------|----------|
| 1 vehicle | 370k | 12 MB | 6 min | Quick test |
| **5 vehicles** | **1.9M** | **58 MB** | **30 min** | **Development** ⭐ |
| **10 vehicles** | **3.7M** | **116 MB** | **60 min** | **Development** ⭐ |
| 20 vehicles | 7.4M | 230 MB | 2 hours | Validation |
| 50 vehicles | 18.5M | 580 MB | 5 hours | Pre-production |
| Full (217) | 80.5M | 2.45 GB | 4-8 hours | Production |

---

## Recommendations

### **For Your Current Project:**

1. **Start with 5-10 vehicles** (~2-4M rows)
   - Fast enough: 30-60 minutes
   - Meaningful: Multiple cycles, diverse patterns
   - Manageable: ~100 MB storage

2. **Create a development subset:**
   ```bash
   # Create data/parquet_dev/ with selected vehicles
   # Use this for all Phase 3-6 development
   ```

3. **Scale up when ready:**
   - Test with 20 vehicles before production
   - Use full dataset for final validation

4. **Keep full dataset available:**
   - Don't delete the full Parquet files
   - Use subset for development
   - Switch to full for production

---

## Next Steps

1. **Create development subset** (5-10 vehicles)
2. **Update Phase 3 script** to use subset by default
3. **Add flag** to switch between dev/prod datasets
4. **Document** which vehicles are in dev subset

**Would you like me to:**
- Create a script to extract 5-10 vehicles to `data/parquet_dev/`?
- Update Phase 3 to use the dev subset by default?
- Add configuration for easy switching between dev/prod?

---

## Conclusion

**Using small data (5-10 vehicles) is the RIGHT approach for development.**

- ✅ Fast iteration
- ✅ Sufficient for meaningful results
- ✅ Easy to scale up later
- ✅ Reduces development time significantly

**Scale up only when:**
- Ready for production validation
- Need statistical power
- Performance testing required

