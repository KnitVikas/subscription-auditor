import { formatDate, formatMoney } from "@/lib/format";
import { Transaction } from "@/lib/types";

export default function ChargesList({ charges }: { charges: Transaction[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">
        Scanned charges <span className="text-sm font-normal text-gray-400">({charges.length})</span>
      </h2>
      {charges.length === 0 ? (
        <p className="rounded-xl border border-dashed border-gray-700 p-8 text-center text-gray-400">
          No charges found in your emails yet. Connect Gmail to scan your inbox.
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-left text-gray-400">
              <tr>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Merchant</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {charges.map((c) => (
                <tr key={c.id} className="border-t border-gray-800">
                  <td className="whitespace-nowrap px-4 py-2 text-gray-400">
                    {formatDate(c.occurred_at)}
                  </td>
                  <td className="px-4 py-2">{c.raw_merchant}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    {formatMoney(c.amount, c.currency, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
