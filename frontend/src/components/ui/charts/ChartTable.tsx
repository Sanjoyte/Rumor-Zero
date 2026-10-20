/**
 * The text alternative of a chart: a visually hidden table. It is a **sibling** of the graphic's
 * `role="img"` element, never a child, because the children of an image are presentational and
 * a screen reader would not find the table inside it.
 */
export interface ChartTableProps {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}

export function ChartTable({ caption, columns, rows }: ChartTableProps) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column} scope="col">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={`${index}:${row[0]}`}>
            {row.map((cell, i) =>
              i === 0 ? (
                <th key={i} scope="row">
                  {cell}
                </th>
              ) : (
                <td key={i}>{cell}</td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
